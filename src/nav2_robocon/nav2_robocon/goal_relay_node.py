"""/move_base_simple/goal (PoseStamped) → Nav2 NavigateToPose action"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose


class GoalRelayNode(Node):
    def __init__(self):
        super().__init__("goal_relay_node")
        self.action_client = ActionClient(self, NavigateToPose, "navigate_to_pose")
        self.sub = self.create_subscription(
            PoseStamped, "/move_base_simple/goal", self.goal_cb, 10)
        self.get_logger().info("GoalRelay: /move_base_simple/goal -> Nav2 NavigateToPose")

    def goal_cb(self, msg: PoseStamped):
        if not self.action_client.wait_for_server(timeout_sec=2.0):
            self.get_logger().error("Nav2 action server not available")
            return

        goal = NavigateToPose.Goal()
        goal.pose = msg
        self.get_logger().info(
            f"Sending goal: ({msg.pose.position.x:.2f}, {msg.pose.position.y:.2f})")
        self.action_client.send_goal_async(goal)


def main(args=None):
    rclpy.init(args=args)
    node = GoalRelayNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
