cmake_minimum_required(VERSION 2.8.3)
project(mmuav_control)

find_package(catkin REQUIRED COMPONENTS
    roscpp
    rospy
    std_msgs
    dynamic_reconfigure
)

find_package(cmake_modules REQUIRED)

generate_dynamic_reconfigure_options(
    # Generic UAV parameters
    config/UavZCtlParams.cfg
    config/UavAttitudeCtlParams.cfg
    # MMUAV parameters
    config/MmuavZCtlParams.cfg
    config/MmuavAttitudeCtlParams.cfg
    # MMCUAV parameters
    config/MmcuavZCtlParams.cfg
    config/MmcuavAttitudeCtlParams.cfg
    # VPC MMCUAV parameters
    config/VpcMmcuavZCtlParams.cfg
    config/VpcMmcuavPositionCtlParams.cfg
    config/VpcMmcuavAttitudeCtlParams.cfg
    config/PositionCtlParams.cfg
    # VPC TTCUAV parameters
    config/VpcTtcuavAttitudeCtlParams.cfg
    config/VpcTtcuavZCtlParams.cfg
    # Rotors variation params
    config/RotorsVariationAttitudeCtlParams.cfg
    # VPC MMUAV parameters
    config/VpcMmuavZCtlParams.cfg
    config/VpcMmuavAttitudeCtlParams.cfg
    config/VpcMmuavPositionCtlParams.cfg
    )
    
catkin_package(
)

include_directories(
  include
  ${catkin_INCLUDE_DIRS}
)

#install(DIRECTORY config
#  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})

#install(DIRECTORY launch
#  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION})