cmake_minimum_required(VERSION 3.8)
project(aurora_ndi_ros2_driver)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

# Generate custom message interfaces
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/AuroraData.msg"
  "msg/AuroraDataVector.msg"
  DEPENDENCIES geometry_msgs std_msgs
)

# Include directories
include_directories(include)

# Create aurora_driver library FIRST
add_library(aurora_driver
  src/ndi_aurora_ros2.cpp
)
target_include_directories(aurora_driver PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
# Link system libraries needed by aurora_driver (for serial communication)
target_link_libraries(aurora_driver pthread)

# Create aurora_utils library
add_library(aurora_utils
  src/aurora_utils.cpp
)
target_include_directories(aurora_utils PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)

# Create the main executable
add_executable(aurora_publisher_node
  src/aurora_publisher_node.cpp
)

# Link libraries to the executable
target_link_libraries(aurora_publisher_node
  aurora_driver
  aurora_utils
)

# Add ament dependencies to the executable
ament_target_dependencies(aurora_publisher_node
  rclcpp
  geometry_msgs
  std_msgs
  tf2_ros
  tf2_geometry_msgs
)

# Link custom message interfaces to the executable
rosidl_get_typesupport_target(cpp_typesupport_target ${PROJECT_NAME} "rosidl_typesupport_cpp")
target_link_libraries(aurora_publisher_node "${cpp_typesupport_target}")

# Install targets
install(TARGETS aurora_publisher_node
  DESTINATION lib/${PROJECT_NAME}
)

# Install directories
install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

install(DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config
  OPTIONAL
)

install(DIRECTORY include/
  DESTINATION include/
)

# Install libraries (in case other packages need them)
install(TARGETS aurora_driver aurora_utils
  EXPORT ${PROJECT_NAME}
  LIBRARY DESTINATION lib
  ARCHIVE DESTINATION lib
  RUNTIME DESTINATION bin
  INCLUDES DESTINATION include
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()