#https://stackoverflow.com/questions/56636714/cuda-compile-problems-on-windows-cmake-error-no-cuda-toolset-found#comment121766428_56665992

"C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat"

# Check if OpenSplat directory exists
if [ ! -d "OpenSplat" ]; then
    git clone https://github.com/pierotofy/OpenSplat OpenSplat
fi

cd OpenSplat
mkdir -p build
cd build

cmake -DCMAKE_PREFIX_PATH=C:/Users/Mega-PC/Desktop/projects/map_to_3d/libtorch -DOPENCV_DIR=C:/Users/Mega-PC/Desktop/projects/map_to_3d/opencv/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_GENERATOR_TOOLSET="cuda=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5" ..
cmake --build . --config Release

cd Release

./opensplat c:/Users/Mega-PC/Desktop/projects/map_to_3d/dataset -n 3000