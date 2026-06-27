"""Custom x/y/yaw action server backed by Nav2 NavigateToPose."""

import math
import threading
import time

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from nav2_robocon_msgs.action import NavigateToXYaw
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Float32


def yaw_to_quat(yaw):
    return math.sin(yaw / 2.0), math.cos(yaw / 2.0)


def quat_to_yaw(q):
    siny = 2.0 * (q.w * q.z + q.x * q.y)
    cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny, cosy)


def goal_id_key(goal_handle):
    return bytes(goal_handle.goal_id.uuid)


class NavigateToXYawServer(Node):
    def __init__(self):
        super().__init__("navigate_to_xyaw_server")

        self.declare_parameter("goal_frame", "nav_map")
        self.declare_parameter("pose_topic", "/odin1/relocation")
        self.declare_parameter("nav_action_name", "navigate_to_pose")
        self.declare_parameter("nav_server_timeout", 2.0)

        self.goal_frame = self.get_parameter("goal_frame").value
        pose_topic = self.get_parameter("pose_topic").value
        nav_action_name = self.get_parameter("nav_action_name").value
        self.nav_server_timeout = float(self.get_parameter("nav_server_timeout").value)

        self.callback_group = ReentrantCallbackGroup()
        self.nav_client = ActionClient(
            self,
            NavigateToPose,
            nav_action_name,
            callback_group=self.callback_group,
        )
        self.action_server = ActionServer(
            self,
            NavigateToXYaw,
            "navigate_to_xyaw",
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.callback_group,
        )

        self.yaw_pub = self.create_publisher(Float32, "/desired_yaw", 10)
        self.pose_sub = self.create_subscription(
            PoseStamped,
            pose_topic,
            self.pose_cb,
            10,
            callback_group=self.callback_group,
        )

        self.lock = threading.RLock()
        self.active_goal_handle = None
        self.nav_goal_handles = {}
        self.preempted_goal_ids = set()
        self.current_x = math.nan
        self.current_y = math.nan
        self.current_yaw = math.nan

        self.get_logger().info(
            "NavigateToXYaw action ready on /navigate_to_xyaw "
            f"(frame={self.goal_frame}, nav_action={nav_action_name})"
        )

    def pose_cb(self, msg):
        self.current_x = msg.pose.position.x
        self.current_y = msg.pose.position.y
        self.current_yaw = quat_to_yaw(msg.pose.orientation)

    def goal_callback(self, goal_request):
        if not all(math.isfinite(v) for v in (goal_request.x, goal_request.y, goal_request.yaw)):
            self.get_logger().warn("Rejecting goal with non-finite x/y/yaw")
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle):
        key = goal_id_key(goal_handle)
        self._cancel_nav_goal(key)
        return CancelResponse.ACCEPT

    def execute_callback(self, goal_handle):
        key = goal_id_key(goal_handle)
        request = goal_handle.request
        result = NavigateToXYaw.Result()

        self._preempt_active_goal(goal_handle)

        if not self._wait_for_nav_server(goal_handle, key, result):
            return result

        self.yaw_pub.publish(Float32(data=float(request.yaw)))
        nav_goal = NavigateToPose.Goal()
        nav_goal.pose = self._make_pose(request.x, request.y, request.yaw)

        self.get_logger().info(
            f"Goal: x={request.x:.2f}, y={request.y:.2f}, "
            f"yaw={math.degrees(request.yaw):.1f}deg"
        )

        send_future = self.nav_client.send_goal_async(
            nav_goal,
            feedback_callback=lambda feedback: self._publish_feedback(goal_handle, feedback),
        )

        if not self._wait_for_future(send_future, goal_handle, key, result):
            return result

        nav_goal_handle = send_future.result()
        if nav_goal_handle is None or not nav_goal_handle.accepted:
            return self._finish_abort(goal_handle, result, "Nav2 rejected goal")

        with self.lock:
            self.nav_goal_handles[key] = nav_goal_handle

        result_future = nav_goal_handle.get_result_async()
        if not self._wait_for_future(result_future, goal_handle, key, result, cancel_nav=True):
            return result

        nav_result = result_future.result()
        status = nav_result.status

        if status == GoalStatus.STATUS_SUCCEEDED:
            result.success = True
            result.nav2_status = int(status)
            result.message = "Goal reached"
            goal_handle.succeed()
            self.get_logger().info("Goal reached")
        else:
            result.success = False
            result.nav2_status = int(status)
            result.message = f"Navigation failed with Nav2 status {status}"
            goal_handle.abort()
            self.get_logger().error(result.message)

        self._release_yaw_if_active(goal_handle)
        self._clear_goal(key)
        return result

    def _preempt_active_goal(self, goal_handle):
        with self.lock:
            previous = self.active_goal_handle
            if previous is not None and previous.is_active and previous != goal_handle:
                previous_key = goal_id_key(previous)
                self.preempted_goal_ids.add(previous_key)
                self._cancel_nav_goal_locked(previous_key)
                self.get_logger().warn("Preempting active goal with newer goal")
            self.active_goal_handle = goal_handle

    def _wait_for_nav_server(self, goal_handle, key, result):
        start_time = time.monotonic()
        while not self.nav_client.wait_for_server(timeout_sec=0.1):
            if self._should_stop(goal_handle, key):
                return self._finish_stopped(goal_handle, key, result)
            if time.monotonic() - start_time > self.nav_server_timeout:
                self._finish_abort(goal_handle, result, "Nav2 action server not available")
                return False
        return True

    def _wait_for_future(self, future, goal_handle, key, result, cancel_nav=False):
        while not future.done():
            if self._should_stop(goal_handle, key):
                if cancel_nav:
                    self._cancel_nav_goal(key)
                return self._finish_stopped(goal_handle, key, result)
            time.sleep(0.05)
        return True

    def _should_stop(self, goal_handle, key):
        with self.lock:
            preempted = key in self.preempted_goal_ids
        return goal_handle.is_cancel_requested or preempted

    def _finish_stopped(self, goal_handle, key, result):
        with self.lock:
            preempted = key in self.preempted_goal_ids
            if preempted:
                self.preempted_goal_ids.discard(key)

        result.success = False
        result.nav2_status = int(GoalStatus.STATUS_CANCELED)

        if goal_handle.is_cancel_requested:
            result.message = "Goal canceled"
            goal_handle.canceled()
            self.get_logger().info(result.message)
        elif preempted:
            result.message = "Goal preempted by newer goal"
            goal_handle.abort()
            self.get_logger().warn(result.message)
        else:
            result.message = "Goal stopped"
            goal_handle.abort()

        self._release_yaw_if_active(goal_handle)
        self._clear_goal(key)
        return False

    def _finish_abort(self, goal_handle, result, message):
        result.success = False
        result.nav2_status = int(GoalStatus.STATUS_ABORTED)
        result.message = message
        goal_handle.abort()
        self.get_logger().error(message)
        self._release_yaw_if_active(goal_handle)
        self._clear_goal(goal_id_key(goal_handle))
        return result

    def _publish_feedback(self, goal_handle, nav_feedback):
        if not goal_handle.is_active:
            return
        feedback = NavigateToXYaw.Feedback()
        feedback.distance_remaining = float(nav_feedback.feedback.distance_remaining)
        feedback.current_x = float(self.current_x)
        feedback.current_y = float(self.current_y)
        feedback.current_yaw = float(self.current_yaw)
        goal_handle.publish_feedback(feedback)

    def _make_pose(self, x, y, yaw):
        pose = PoseStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = self.goal_frame
        pose.pose.position.x = float(x)
        pose.pose.position.y = float(y)
        qz, qw = yaw_to_quat(float(yaw))
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw
        return pose

    def _cancel_nav_goal(self, key):
        with self.lock:
            self._cancel_nav_goal_locked(key)

    def _cancel_nav_goal_locked(self, key):
        nav_goal_handle = self.nav_goal_handles.get(key)
        if nav_goal_handle is not None:
            nav_goal_handle.cancel_goal_async()

    def _clear_goal(self, key):
        with self.lock:
            self.nav_goal_handles.pop(key, None)
            if self.active_goal_handle is not None and goal_id_key(self.active_goal_handle) == key:
                self.active_goal_handle = None

    def _release_yaw_if_active(self, goal_handle):
        with self.lock:
            is_active_goal = self.active_goal_handle is not None and self.active_goal_handle == goal_handle
        if is_active_goal:
            self.yaw_pub.publish(Float32(data=math.nan))


def main(args=None):
    rclpy.init(args=args)
    node = NavigateToXYawServer()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
