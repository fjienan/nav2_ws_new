"""Nav2 Bringup for ROBOCON omnidirectional robot."""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory("nav2_robocon")

    team = LaunchConfiguration("team")
    params_file = LaunchConfiguration("params_file")
    map_file = LaunchConfiguration("map")
    use_ramp_safety = LaunchConfiguration("use_ramp_safety")

    team_arg = DeclareLaunchArgument(
        "team", default_value="red",
        description="Team color: red or blue"
    )
    params_file_arg = DeclareLaunchArgument(
        "params_file",
        default_value=os.path.join(pkg_dir, "config", "nav2_params.yaml"),
        description="Full path to the Nav2 parameters file",
    )
    map_arg = DeclareLaunchArgument(
        "map",
        default_value=[pkg_dir, "/maps/field_", team, ".yaml"],
        description="Full path to the map yaml file",
    )
    use_ramp_safety_arg = DeclareLaunchArgument(
        "use_ramp_safety",
        default_value="true",
        description="Enable ramp suspension, speed, and yaw safety filtering",
    )

    # --- odom_to_tf_node: relocation → TF map→base_link ---
    odom_to_tf = Node(
        package="nav2_robocon",
        executable="odom_to_tf_node",
        name="odom_to_tf_node",
        output="screen",
        parameters=[{
            "pose_topic": "/odin1/relocation",
            "parent_frame": "nav_map",
            "child_frame": "base_link",
        }],
    )

    # --- cmd_vel_bridge: /cmd_vel_adjusted → /t0x0101_action ---
    cmd_vel_bridge_adjusted = Node(
        package="nav2_robocon",
        executable="cmd_vel_bridge",
        name="cmd_vel_bridge",
        output="screen",
        remappings=[("/cmd_vel", "/cmd_vel_adjusted")],
        condition=IfCondition(use_ramp_safety),
    )

    # --- cmd_vel_bridge direct path when ramp safety is disabled ---
    cmd_vel_bridge_direct = Node(
        package="nav2_robocon",
        executable="cmd_vel_bridge",
        name="cmd_vel_bridge",
        output="screen",
        condition=UnlessCondition(use_ramp_safety),
    )

    # --- ramp_zone_manager ---
    ramp_zone_manager = Node(
        package="nav2_robocon",
        executable="ramp_zone_manager",
        name="ramp_zone_manager",
        output="screen",
        parameters=[{"team": team}],
        condition=IfCondition(use_ramp_safety),
    )

    # --- x/y/yaw action server ---
    navigate_to_xyaw = Node(
        package="nav2_robocon",
        executable="navigate_to_xyaw_server",
        name="navigate_to_xyaw_server",
        output="screen",
        parameters=[{
            "goal_frame": "nav_map",
            "pose_topic": "/odin1/relocation",
        }],
    )

    # --- Nav2 核心（map_server + planner + controller + bt_navigator + lifecycle） ---
    # map_server 单独启动，传入 team 对应的地图
    map_server = Node(
        package="nav2_map_server",
        executable="map_server",
        name="map_server",
        output="screen",
        parameters=[
            params_file,
            {"yaml_filename": map_file},
        ],
    )

    # Nav2 controller, planner, bt_navigator
    controller_server = Node(
        package="nav2_controller",
        executable="controller_server",
        name="controller_server",
        output="screen",
        parameters=[params_file],
    )

    planner_server = Node(
        package="nav2_planner",
        executable="planner_server",
        name="planner_server",
        output="screen",
        parameters=[params_file],
    )

    behavior_server = Node(
        package="nav2_behaviors",
        executable="behavior_server",
        name="behavior_server",
        output="screen",
        parameters=[params_file],
    )

    waypoint_follower = Node(
        package="nav2_waypoint_follower",
        executable="waypoint_follower",
        name="waypoint_follower",
        output="screen",
        parameters=[params_file],
    )

    bt_navigator = Node(
        package="nav2_bt_navigator",
        executable="bt_navigator",
        name="bt_navigator",
        output="screen",
        parameters=[params_file],
    )

    lifecycle_manager = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager",
        name="lifecycle_manager",
        output="screen",
        parameters=[params_file],
    )

    return LaunchDescription([
        team_arg,
        params_file_arg,
        map_arg,
        use_ramp_safety_arg,
        odom_to_tf,
        cmd_vel_bridge_adjusted,
        cmd_vel_bridge_direct,
        ramp_zone_manager,
        navigate_to_xyaw,
        map_server,
        controller_server,
        planner_server,
        behavior_server,
        waypoint_follower,
        bt_navigator,
        lifecycle_manager,
    ])
