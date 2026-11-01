"""ジェスチャ生成ノードと実行ノードを起動する（Gazebo は別途 crane_plus_with_table.launch.py で起動）."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('model', default_value='', description='Gemini model (empty: .env / default)'),
        DeclareLaunchArgument('env_file', default_value='/workspace/.env'),
        Node(package='crane_gesture', executable='gesture_planner', output='screen',
             parameters=[{'model': LaunchConfiguration('model'),
                          'env_file': LaunchConfiguration('env_file')}]),
        Node(package='crane_gesture', executable='gesture_executor', output='screen'),
    ])
