from glob import glob

from setuptools import setup

package_name = 'crane_gesture'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/rviz', glob('rviz/*.rviz')),
        ('share/' + package_name + '/scripts', glob('scripts/*.sh')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    description='LLM (Gemini) generates expressive gestures for CRANE+ V2',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'gesture_planner = crane_gesture.planner_node:main',
            'gesture_executor = crane_gesture.executor_node:main',
            'chat = crane_gesture.chat_cli:main',
            'caption = crane_gesture.caption_node:main',
            'record_demo = crane_gesture.record_demo:main',
        ],
    },
)
