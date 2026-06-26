"""Nav2 Bringup for ROBOCON omnidirectional robot."""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory("nav2_robocon")
    nav2_bringup_dir = get_package_share_directory("nav2_bringup")

    team = LaunchConfiguration("team", default="red")

    team_arg = DeclareLaunchArgument(
        "team", default_value="red",
        description="Team color: red or blue"
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
    cmd_vel_bridge = Node(
        package="nav2_robocon",
        executable="cmd_vel_bridge",
        name="cmd_vel_bridge",
        output="screen",
        remappings=[("/cmd_vel", "/cmd_vel_adjusted")],
    )

    # --- ramp_zone_manager ---
    ramp_zone_manager = Node(
        package="nav2_robocon",
        executable="ramp_zone_manager",
        name="ramp_zone_manager",
        output="screen",
        parameters=[{"team": team}],
    )

    # --- goal_relay_node ---
    goal_relay = Node(
        package="nav2_robocon",
        executable="goal_relay_node",
        name="goal_relay_node",
        output="screen",
    )

    # --- Nav2 核心（map_server + planner + controller + bt_navigator + lifecycle） ---
    nav2_params = os.path.join(pkg_dir, "config", "nav2_params.yaml")

    # map_server 单独启动，传入 team 对应的地图
    map_server = Node(
        package="nav2_map_server",
        executable="map_server",
        name="map_server",
        output="screen",
        parameters=[
            nav2_params,
            {"yaml_filename": PathJoinSubstitution([pkg_dir, "maps", ["field_", team, ".yaml"]])},
        ],
    )

    # Nav2 controller, planner, bt_navigator
    controller_server = Node(
        package="nav2_controller",
        executable="controller_server",
        name="controller_server",
        output="screen",
        parameters=[nav2_params],
    )

    planner_server = Node(
        package="nav2_planner",
        executable="planner_server",
        name="planner_server",
        output="screen",
        parameters=[nav2_params],
    )

    behavior_server = Node(
        package="nav2_behaviors",
        executable="behavior_server",
        name="behavior_server",
        output="screen",
        parameters=[nav2_params],
    )

    waypoint_follower = Node(
        package="nav2_waypoint_follower",
        executable="waypoint_follower",
        name="waypoint_follower",
        output="screen",
        parameters=[nav2_params],
    )

    bt_navigator = Node(
        package="nav2_bt_navigator",
        executable="bt_navigator",
        name="bt_navigator",
        output="screen",
        parameters=[nav2_params],
    )

    lifecycle_manager = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager",
        name="lifecycle_manager",
        output="screen",
        parameters=[nav2_params],
    )

    return LaunchDescription([
        team_arg,
        odom_to_tf,
        cmd_vel_bridge,
        ramp_zone_manager,
        goal_relay,
        map_server,
        controller_server,
        planner_server,
        behavior_server,
        waypoint_follower,
        bt_navigator,
        lifecycle_manager,
    ])
