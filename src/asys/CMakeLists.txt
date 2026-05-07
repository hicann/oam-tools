cmake_minimum_required(VERSION 3.15)
project(Asys)
 
message(${CMAKE_CURRENT_SOURCE_DIR})
set(ASYS_DIR ${CMAKE_CURRENT_SOURCE_DIR})
 
include(${CMAKE_CURRENT_SOURCE_DIR}/asys.cmake)
 
install(DIRECTORY
    ${ASYS_DIR}
    DESTINATION ${INSTALL_LIBRARY_DIR} OPTIONAL
)