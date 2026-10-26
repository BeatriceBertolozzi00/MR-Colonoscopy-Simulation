#!/usr/bin/env python3

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import (
    DeclareLaunchArgument, 
    LogInfo,
    ExecuteProcess
)
from launch.substitutions import (
    LaunchConfiguration, 
    PathJoinSubstitution
)
from launch_ros.substitutions import FindPackageShare
from launch.conditions import IfCondition

def generate_launch_description():
    # =============================================================================
    # LAUNCH ARGUMENTS
    # =============================================================================
    serial_port_arg = DeclareLaunchArgument(
        'serial_port',
        default_value='/dev/ttyUSB0',
        description='Aurora serial port'
    )
    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value=PathJoinSubstitution([
            FindPackageShare('aurora_ndi_ros2_driver'),
            'config',
            'aurora_config.yaml'
        ]),
        description='Path to Aurora configuration YAML file'
    )
    
    debug_arg = DeclareLaunchArgument(
        'debug',
        default_value='false',
        choices=['true', 'false'],
        description='Enable debug mode with verbose logging'
    )
    
    log_level_arg = DeclareLaunchArgument(
        'log_level',
        default_value='info',
        choices=['debug', 'info', 'warn', 'error'],
        description='ROS logging level'
    )
    
    use_rviz_arg = DeclareLaunchArgument(
        'use_rviz',
        default_value='false',
        choices=['true', 'false'],
        description='Launch RViz for Aurora pose visualization'
    )
    
    publish_tf_arg = DeclareLaunchArgument(
        'publish_tf',
        default_value='true',
        choices=['true', 'false'],
        description='Publish static transform from world to aurora_base'
    )
    
    namespace_arg = DeclareLaunchArgument(
        'namespace',
        default_value='',
        description='ROS namespace for Aurora node (optional)'
    )
    
    # =============================================================================
    # MAIN AURORA PUBLISHER NODE
    # =============================================================================
    
    aurora_publisher_node = Node(
        package='aurora_ndi_ros2_driver',
        executable='aurora_publisher_node',
        name='aurora_publisher_node',
        namespace=LaunchConfiguration('namespace'),
        parameters=[
        LaunchConfiguration('config_file'),
        {'serial_port': LaunchConfiguration('serial_port')}],
        arguments=[
            '--ros-args', 
            '--log-level', LaunchConfiguration('log_level')
        ],
        output='screen',
        emulate_tty=True,
        respawn=True,
        respawn_delay=3
    )
    
    # =============================================================================
    # STATIC TRANSFORM PUBLISHER 
    # =============================================================================
    
    static_tf_publisher = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='aurora_base_tf_publisher',
        arguments=[
            '0', '0', '0',      # translation x, y, z (meters)
             '0', '0.7071', '0', '0.7071', # rotation x, y, z, w (quaternion)
            'world',            # parent frame
            'aurora_base'       # child frame  
        ],
        output='log',
        condition=IfCondition(LaunchConfiguration('publish_tf'))
    )
    
    # =============================================================================
    # RVIZ VISUALIZATION
    # =============================================================================
    
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='aurora_rviz',
        arguments=[
            '-d', PathJoinSubstitution([
                FindPackageShare('aurora_ndi_ros2_driver'),
                'config',
                'aurora_viz.rviz'
            ])
        ],
        output='log',
        condition=IfCondition(LaunchConfiguration('use_rviz'))
    )
    
    # =============================================================================
    # DEBUG MONITORING (only if debug=true)
    # =============================================================================
    
    topic_monitor = ExecuteProcess(
        cmd=[
            'ros2', 'topic', 'hz', '/aurora_data', 
            '--window', '50', '--wall-time'
        ],
        output='screen',
        condition=IfCondition(LaunchConfiguration('debug'))
    )
    
    # =============================================================================
    # LAUNCH DESCRIPTION
    # =============================================================================
    
    return LaunchDescription([
        # Arguments
        config_file_arg,
        serial_port_arg,
        debug_arg,
        log_level_arg,
        use_rviz_arg,
        publish_tf_arg,
        namespace_arg,
        
        # Log startup info
        LogInfo(msg="=== Aurora Publisher Starting ==="),
        LogInfo(msg=["Config: ", LaunchConfiguration('config_file')]),
        LogInfo(msg=["Debug: ", LaunchConfiguration('debug')]),
        LogInfo(msg=["RViz: ", LaunchConfiguration('use_rviz')]),
        LogInfo(msg="==================================="),
        
        # Main nodes
        aurora_publisher_node,
        static_tf_publisher,
        rviz_node,
        
        # Debug tools
        topic_monitor,
        
        # Final log
        LogInfo(msg="Aurora Publisher launch complete!")
    ])
