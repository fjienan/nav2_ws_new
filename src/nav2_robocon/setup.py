from setuptools import setup
import os
from glob import glob

package_name = "nav2_robocon"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
        (os.path.join("share", package_name, "maps"), glob("maps/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    entry_points={
        "console_scripts": [
            "odom_to_tf_node = nav2_robocon.odom_to_tf_node:main",
            "cmd_vel_bridge = nav2_robocon.cmd_vel_bridge:main",
            "ramp_zone_manager = nav2_robocon.ramp_zone_manager:main",
            "goal_relay_node = nav2_robocon.goal_relay_node:main",
            "navigate_to_xyaw_server = nav2_robocon.navigate_to_xyaw_server:main",
            "third_area_single = nav2_robocon.third_area_single:main",
        ],
    },
)
