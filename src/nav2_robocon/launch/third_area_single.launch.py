"""启动 Nav2 + 单目标导航节点（监听 /single_nav_goal）"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_dir = get_package_share_directory("nav2_robocon")
    team = LaunchConfiguration("team", default="red")

    team_arg = DeclareLaunchArgument("team", default_value="red")

    # 包含 Nav2 bringup
    nav2_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_dir, "launch", "nav2_bringup.launch.py")
        ),
        launch_arguments={"team": team}.items(),
    )

    # 延迟启动任务节点（等 Nav2 就绪）
    task_node = TimerAction(
        period=5.0,
        actions=[
            Node(
                package="nav2_robocon",
                executable="third_area_single",
                name="third_area_single",
                output="screen",
                parameters=[{"team": team}],
            )
        ],
    )

    return LaunchDescription([
        team_arg,
        nav2_bringup,
        task_node,
    ])
