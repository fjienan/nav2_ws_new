"""启动 Nav2 + x/y/yaw action server."""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


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

    return LaunchDescription([
        team_arg,
        nav2_bringup,
    ])
