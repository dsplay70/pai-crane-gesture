"""動画撮影用: ジェスチャ生成・実行ノード + デモ用 RViz + 字幕パネル + ウィンドウ配置.

Gazebo は別途 `ros2 launch crane_plus_gazebo crane_plus_with_table.launch.py` で起動しておく。
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory('crane_gesture')
    return LaunchDescription([
        DeclareLaunchArgument('model', default_value=''),
        DeclareLaunchArgument('caption_height', default_value='260'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(share, 'launch', 'gesture.launch.py')),
            launch_arguments={'model': LaunchConfiguration('model')}.items()),
        Node(package='rviz2', executable='rviz2', name='demo_rviz', output='log',
             arguments=['-d', os.path.join(share, 'rviz', 'demo.rviz')]),
        Node(package='crane_gesture', executable='caption', output='screen'),
        TimerAction(period=3.0, actions=[ExecuteProcess(
            cmd=[os.path.join(share, 'scripts', 'arrange_windows.sh')],
            additional_env={'CAPTION_H': LaunchConfiguration('caption_height')},
            output='screen')]),
    ])
