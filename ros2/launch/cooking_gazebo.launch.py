# DetachableJoint 版の launch（食材を先に、ロボットを後に生成する）
import os

from ament_index_python.packages import get_package_share_directory
from crane_plus_description.robot_description_loader import RobotDescriptionLoader
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch.actions import IncludeLaunchDescription
from launch.actions import TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.actions import SetParameter

MODEL = '/home/ubuntu/cooking/model/crane_plus_dj.sdf'


def generate_launch_description():
    env = {'IGN_GAZEBO_SYSTEM_PLUGIN_PATH': os.environ['LD_LIBRARY_PATH'],
           'IGN_GAZEBO_RESOURCE_PATH': os.path.dirname(
               get_package_share_directory('crane_plus_description'))}
    world_file = os.path.join(
        get_package_share_directory('crane_plus_gazebo'), 'worlds', 'table.sdf')
    gui_config = os.path.join(
        get_package_share_directory('crane_plus_gazebo'), 'gui', 'gui.config')

    ign_gazebo = ExecuteProcess(
        cmd=['ign gazebo -r', world_file, '--gui-config', gui_config],
        output='screen', additional_env=env, shell=True)

    # 食材 -> ロボット の順に生成（プラグインは child_model が存在する前提のため）
    spawn_food = ExecuteProcess(
        cmd=['bash', '/home/ubuntu/cooking/spawn_food.sh'],
        output='screen', shell=True)

    spawn_robot = Node(
        package='ros_gz_sim', executable='create', output='screen',
        arguments=['-file', MODEL, '-name', 'crane_plus', '-z', '1.015',
                   '-allow_renaming', 'true'])

    description_loader = RobotDescriptionLoader()
    description_loader.use_gazebo = 'true'
    description_loader.use_ignition = 'true'
    description_loader.gz_control_config_package = 'crane_plus_control'
    description_loader.gz_control_config_file_path = 'config/crane_plus_controllers.yaml'
    description = description_loader.load()

    move_group = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            get_package_share_directory('crane_plus_moveit_config'),
            '/launch/run_move_group.launch.py']),
        launch_arguments={'loaded_description': description}.items())

    spawn_js = ExecuteProcess(
        cmd=['ros2 run controller_manager spawner joint_state_broadcaster --controller-manager-timeout 60'],
        shell=True, output='screen')
    spawn_arm = ExecuteProcess(
        cmd=['ros2 run controller_manager spawner crane_plus_arm_controller --controller-manager-timeout 60'],
        shell=True, output='screen')
    spawn_grip = ExecuteProcess(
        cmd=['ros2 run controller_manager spawner crane_plus_gripper_controller --controller-manager-timeout 60'],
        shell=True, output='screen')

    bridge = Node(
        package='ros_gz_bridge', executable='parameter_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock'],
        output='screen')

    return LaunchDescription([
        SetParameter(name='use_sim_time', value=True),
        ign_gazebo,
        TimerAction(period=6.0, actions=[spawn_food]),
        TimerAction(period=14.0, actions=[spawn_robot]),
        move_group,
        TimerAction(period=24.0, actions=[spawn_js, spawn_arm, spawn_grip]),
        bridge,
    ])
