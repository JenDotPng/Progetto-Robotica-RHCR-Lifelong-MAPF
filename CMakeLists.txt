cmake_minimum_required(VERSION 3.12...3.30)
project(RHCR CXX)

# Imposta lo standard C++11
set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# new
# Configurazione specifica per Windows MSVC
if(MSVC)
    # Abilita gli operatori testuali (and, or, not) su Visual Studio
    add_compile_options(/permissive-)
endif()

# Configurazione specifica per macOS
if(APPLE)
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -stdlib=libc++ -I/usr/local/include")
    execute_process(COMMAND xcrun --show-sdk-path
                    OUTPUT_VARIABLE SDK_PATH
                    OUTPUT_STRIP_TRAILING_WHITESPACE)
    set(CMAKE_OSX_SYSROOT ${SDK_PATH})
    include_directories(SYSTEM "${SDK_PATH}/usr/include/c++/v1")
endif()

# Policy per compatibilità con FindBoost legacy
if(POLICY CMP0167)
    cmake_policy(SET CMP0167 OLD)
endif()

# Trova Boost
set(Boost_NO_BOOST_CMAKE ON)
find_package(Boost REQUIRED COMPONENTS program_options filesystem)

# Raccogli tutti i file sorgente
file(GLOB SOURCES "src/*.cpp")

# Crea l'eseguibile
add_executable(lifelong ${SOURCES})

# Imposta le directory di inclusione per il target
target_include_directories(lifelong
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/inc
        ${Boost_INCLUDE_DIRS}
)

# Collega le librerie Boost
target_link_libraries(lifelong
    PRIVATE
        Boost::program_options
        Boost::filesystem
)