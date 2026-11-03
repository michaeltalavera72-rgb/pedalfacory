cmake_minimum_required(VERSION 3.22)
project(VirtualPedalboard VERSION 0.1.0)
set(CMAKE_CXX_STANDARD 17)
include(FetchContent)
FetchContent_Declare(JUCE GIT_REPOSITORY https://github.com/juce-framework/JUCE.git GIT_TAG 8.0.15 GIT_SHALLOW TRUE)   # 8.0.15: newest JUCE 8, works with VS 2026
FetchContent_MakeAvailable(JUCE)

juce_add_plugin(VirtualPedalboard
    COMPANY_NAME "YourCompany"
    PLUGIN_MANUFACTURER_CODE Ypcm
    PLUGIN_CODE Vpbd
    FORMATS VST3 Standalone
    PRODUCT_NAME "Virtual Pedalboard"
    IS_SYNTH FALSE NEEDS_MIDI_INPUT FALSE NEEDS_MIDI_OUTPUT FALSE
    COPY_PLUGIN_AFTER_BUILD FALSE)   # TRUE copies to Program Files\Common Files\VST3 (needs admin)

target_sources(VirtualPedalboard PRIVATE
    Source/PluginProcessor.cpp Source/PluginEditor.cpp Source/Faces/PedalFaces.cpp)

# Fonts/images compiled into the plugin (BinaryData::...). Alfa Slab One: SIL Open Font License.
# Assets/Ramhorn/*.png come from Tools/Blender/render_ramhorn.py; if they're missing the face is drawn in vector.
file(GLOB PEDAL_RENDERS CONFIGURE_DEPENDS Assets/Ramhorn/*.png Assets/Buzzsaw/*.png Assets/RailBender/*.png Assets/ValveHowler/*.png Assets/FeralHound/*.png Assets/SlowBurn/*.png)
juce_add_binary_data(PedalboardAssets SOURCES Assets/AlfaSlabOne-Regular.ttf Assets/MetalMania-Regular.ttf Assets/Rye-Regular.ttf Assets/Poppins-BoldItalic.ttf Assets/BlackOpsOne-Regular.ttf Assets/CinzelDecorative-Bold.ttf Assets/feralhound_dog.png ${PEDAL_RENDERS})
target_include_directories(VirtualPedalboard PRIVATE Source)
target_compile_definitions(VirtualPedalboard PUBLIC
    JUCE_WEB_BROWSER=0 JUCE_USE_CURL=0 JUCE_VST3_CAN_REPLACE_VST2=0
    JUCE_ASIO=1)   # ASIO drivers in the Standalone (Windows only). Uses the ASIO SDK bundled with JUCE (GPLv3 / Steinberg license)
target_link_libraries(VirtualPedalboard PRIVATE
    PedalboardAssets juce::juce_audio_utils juce::juce_dsp
    juce::juce_recommended_config_flags juce::juce_recommended_warning_flags)
