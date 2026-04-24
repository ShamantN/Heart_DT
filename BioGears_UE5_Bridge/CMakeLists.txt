cmake_minimum_required(VERSION 3.16)
project(BioGearsBridge)

set(CMAKE_CXX_STANDARD 20)

# 1. Download the Eigen3 math headers (BioGears requires this to compile)
include(FetchContent)
FetchContent_Declare(
  eigen
  URL https://gitlab.com/libeigen/eigen/-/archive/3.4.0/eigen-3.4.0.zip
)
FetchContent_MakeAvailable(eigen)

# 2. Define your executable
add_executable(bridge main.cpp)

# 3. Hardcode the path to the BioGears Header Files
target_include_directories(bridge PRIVATE 
    "C:/Users/shama/Documents/BioGears_UE5_Bridge/biogears_include"
    "C:/Users/shama/Documents/XSD_TempZip/xsd-4.0.0-i686-windows/libxsd"
    "C:/Users/shama/Documents/Xerces_TempZip/xerces-c-3.2.4/src"
)

# 4. Hardcode the path to the Pre-Compiled BioGears Library Files
target_link_libraries(bridge PRIVATE 
    "C:/Program Files/BioGears/lib/biogears.lib"
    "C:/Program Files/BioGears/lib/biogears_cdm.lib"
    "C:/Program Files/BioGears/lib/biogears_io.lib"
    "C:/Program Files/BioGears/lib/libbiogears_common_st.lib"
    "C:/Users/shama/Documents/Xerces_TempZip/xerces-c-3.2.4/src/Debug/xerces-c_3D.lib"
    eigen
    ws2_32
)