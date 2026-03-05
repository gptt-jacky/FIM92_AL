#include <iostream>
#include <iomanip>
#include <sstream>
#include <vector>
#include <fstream>
#include <string>
#include <map>
#include <filesystem>

#include <Antilatency.InterfaceContract.LibraryLoader.h>
#include <Antilatency.DeviceNetwork.h>
#include <Antilatency.HardwareExtensionInterface.h>
#include <Antilatency.HardwareExtensionInterface.Interop.h>
#if defined(__linux__)
	#include <dlfcn.h>
#endif
#if defined(_WIN32)
	#include <conio.h>
#endif
#include <thread>
#include <chrono>

// ============================================================
// Scene configuration
// ============================================================
struct SceneConfig {
    std::string name;
    std::string environmentData;
    std::string placementData;
};

// ============================================================
// Per-tracker instance (supports multiple Alt devices)
// ============================================================
struct TrackerInstance {
    Antilatency::DeviceNetwork::NodeHandle node;
    Antilatency::Alt::Tracking::ITrackingCotask cotask;
    int id;
    std::string type;  // Type read from AntilatencyService (e.g. "Stinger", "Binoculars")
    std::string number; // Number read from AntilatencyService
};

// Per-HW-Extension instance (supports multiple IO modules)
struct HWExtInstance {
    Antilatency::DeviceNetwork::NodeHandle node;
    Antilatency::HardwareExtensionInterface::ICotask cotask;
    std::string type;
    std::vector<Antilatency::HardwareExtensionInterface::IInputPin> inputPins;
    Antilatency::HardwareExtensionInterface::IOutputPin outputPinIO7;
    bool io7State = false;
    Antilatency::HardwareExtensionInterface::IOutputPin outputPinIO8;  // Tag B only (大震動)
    bool io8State = false;
    bool hasIO8Output = false;  // true only for Tag B
};

// ============================================================
// Simple JSON parser for scenes.json
// Supports format:
// {
//   "scenes": [
//     { "name": "...", "environmentData": "...", "placementData": "..." },
//     ...
//   ]
// }
// ============================================================
static std::string trimQuotes(const std::string& s) {
    if (s.size() >= 2 && s.front() == '"' && s.back() == '"') {
        return s.substr(1, s.size() - 2);
    }
    return s;
}

static std::string extractJsonValue(const std::string& json, const std::string& key) {
    std::string search = "\"" + key + "\"";
    auto pos = json.find(search);
    if (pos == std::string::npos) return "";
    pos = json.find(':', pos + search.size());
    if (pos == std::string::npos) return "";
    pos++;
    while (pos < json.size() && (json[pos] == ' ' || json[pos] == '\t' || json[pos] == '\n' || json[pos] == '\r')) pos++;
    if (pos >= json.size()) return "";
    if (json[pos] == '"') {
        auto end = json.find('"', pos + 1);
        if (end == std::string::npos) return "";
        return json.substr(pos + 1, end - pos - 1);
    }
    auto end = json.find_first_of(",}\n\r", pos);
    return json.substr(pos, end - pos);
}

static std::vector<SceneConfig> parseSceneConfigs(const std::string& filename) {
    std::vector<SceneConfig> scenes;
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Cannot open config file: " << filename << std::endl;
        return scenes;
    }
    std::string content((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    file.close();

    // Find all scene objects within "scenes" array
    auto arrStart = content.find('[');
    auto arrEnd = content.rfind(']');
    if (arrStart == std::string::npos || arrEnd == std::string::npos) return scenes;

    std::string arr = content.substr(arrStart + 1, arrEnd - arrStart - 1);

    size_t pos = 0;
    while (pos < arr.size()) {
        auto objStart = arr.find('{', pos);
        if (objStart == std::string::npos) break;
        auto objEnd = arr.find('}', objStart);
        if (objEnd == std::string::npos) break;

        std::string obj = arr.substr(objStart, objEnd - objStart + 1);
        SceneConfig sc;
        sc.name = extractJsonValue(obj, "name");
        sc.environmentData = extractJsonValue(obj, "environmentData");
        sc.placementData = extractJsonValue(obj, "placementData");

        if (!sc.environmentData.empty()) {
            if (sc.name.empty()) sc.name = "Scene " + std::to_string(scenes.size() + 1);
            if (sc.placementData.empty()) sc.placementData = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
            scenes.push_back(sc);
        }
        pos = objEnd + 1;
    }
    return scenes;
}

// ============================================================
// Read Type from a device node (returns "" if not set)
// ============================================================
static std::string getNodeType(Antilatency::DeviceNetwork::INetwork network, Antilatency::DeviceNetwork::NodeHandle node) {
    try {
        return network.nodeGetStringProperty(node, "Type");
    } catch (...) {
        return "";
    }
}

// ============================================================
// Read Number from a device node (returns "" if not set)
// ============================================================
static std::string getNodeNumber(Antilatency::DeviceNetwork::INetwork network, Antilatency::DeviceNetwork::NodeHandle node) {
    try {
        return network.nodeGetStringProperty(node, "Number");
    } catch (...) {
        return "";
    }
}

// ============================================================
// Find ALL idle tracking nodes (not just the first)
// ============================================================
std::vector<Antilatency::DeviceNetwork::NodeHandle> getAllIdleTrackingNodes(
    Antilatency::DeviceNetwork::INetwork network,
    Antilatency::Alt::Tracking::ITrackingCotaskConstructor altTrackingCotaskConstructor)
{
    std::vector<Antilatency::DeviceNetwork::NodeHandle> result;
    std::vector<Antilatency::DeviceNetwork::NodeHandle> altNodes = altTrackingCotaskConstructor.findSupportedNodes(network);
    for (auto node : altNodes) {
        if (network.nodeGetStatus(node) == Antilatency::DeviceNetwork::NodeStatus::Idle) {
            result.push_back(node);
        }
    }
    return result;
}

Antilatency::DeviceNetwork::NodeHandle getIdleExtensionNode(
    Antilatency::DeviceNetwork::INetwork network,
    Antilatency::HardwareExtensionInterface::ICotaskConstructor hwCotaskConstructor)
{
    std::vector<Antilatency::DeviceNetwork::NodeHandle> hwNodes = hwCotaskConstructor.findSupportedNodes(network);
    for (auto node : hwNodes) {
        if (network.nodeGetStatus(node) == Antilatency::DeviceNetwork::NodeStatus::Idle) {
            return node;
        }
    }
    return Antilatency::DeviceNetwork::NodeHandle::Null;
}

std::vector<Antilatency::DeviceNetwork::NodeHandle> getAllIdleExtensionNodes(
    Antilatency::DeviceNetwork::INetwork network,
    Antilatency::HardwareExtensionInterface::ICotaskConstructor hwCotaskConstructor)
{
    std::vector<Antilatency::DeviceNetwork::NodeHandle> result;
    std::vector<Antilatency::DeviceNetwork::NodeHandle> hwNodes = hwCotaskConstructor.findSupportedNodes(network);
    for (auto node : hwNodes) {
        if (network.nodeGetStatus(node) == Antilatency::DeviceNetwork::NodeStatus::Idle) {
            result.push_back(node);
        }
    }
    return result;
}

#if defined(__linux__)
std::string getParentPath(const char *inp){
    auto len = strlen(inp);
    if(len == 0) throw std::runtime_error("no parent path: " + std::string(inp));
    int i = len - 1;
    while(i > 0){
        if(inp[i] == '/'){
            return std::string(inp, inp + i + 1);
        }
        --i;
    }
    throw std::runtime_error("no parent path: " + std::string(inp));
}
#endif

// ============================================================
// Tag = Type property directly (A/B/C/D set in AntilatencyService)
// ============================================================
static std::string typeToTag(const std::string& type) {
    if (type == "A" || type == "B" || type == "C" || type == "D" || type == "E" || type == "F") return type;
    return "";  // Unknown type, no tag
}

// ============================================================
// Check for keyboard input (non-blocking)
// ============================================================
static int getKeyPress() {
#if defined(_WIN32)
    if (_kbhit()) {
        return _getch();
    }
#endif
    return -1;
}

// ============================================================
// Switch scene: stop all trackers, create new environment
// ============================================================
static bool switchScene(
    int sceneIndex,
    const std::vector<SceneConfig>& scenes,
    Antilatency::Alt::Environment::Selector::ILibrary& environmentSelectorLibrary,
    Antilatency::Alt::Tracking::ILibrary& altTrackingLibrary,
    Antilatency::Alt::Environment::IEnvironment& currentEnvironment,
    Antilatency::Math::floatP3Q& currentPlacement,
    std::vector<TrackerInstance>& trackers)
{
    if (sceneIndex < 0 || sceneIndex >= static_cast<int>(scenes.size())) {
        return false;
    }

    // Stop all active tracking cotasks
    for (auto& t : trackers) {
        t.cotask = nullptr;
    }
    trackers.clear();

    // Create new environment
    const auto& scene = scenes[sceneIndex];
    auto newEnv = environmentSelectorLibrary.createEnvironment(scene.environmentData);
    if (newEnv == nullptr) {
        std::cerr << "\nFailed to create environment for scene: " << scene.name << std::endl;
        return false;
    }

    currentEnvironment = newEnv;
    currentPlacement = altTrackingLibrary.createPlacement(scene.placementData);

    std::cout << "\n>> Switched to scene [" << (sceneIndex + 1) << "]: " << scene.name << std::endl;
    return true;
}

// ============================================================
// Print usage
// ============================================================
static void printUsage(const std::string& progName) {
    std::cout << "Usage:" << std::endl;
    std::cout << "  " << progName << " <config.json>              -- Load scenes from config file" << std::endl;
    std::cout << "  " << progName << " <envData> <placementData>  -- Single scene (legacy mode)" << std::endl;
    std::cout << std::endl;
    std::cout << "Runtime controls:" << std::endl;
    std::cout << "  [1]-[9]  Switch to scene 1-9" << std::endl;
    std::cout << "  [L]      List available scenes" << std::endl;
    std::cout << "  [A]      Toggle IO7 Tag A (後座力)" << std::endl;
    std::cout << "  [B]      Toggle IO7 Tag B (小震動)" << std::endl;
    std::cout << "  [C]      Toggle IO8 Tag B (大震動)" << std::endl;
    std::cout << "  [O]      Toggle IO7 all devices" << std::endl;
    std::cout << "  [Q]      Quit" << std::endl;
}

// ============================================================
// MAIN
// ============================================================
int main(int argc, char* argv[]) {
    // ---- Parse arguments ----
    std::vector<SceneConfig> scenes;
    bool jsonMode = false;  // --json mode: output JSON to stdout only, no file write

    // Check --json flag
    std::vector<std::string> args;
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--json" || arg == "-j") {
            jsonMode = true;
        } else {
            args.push_back(arg);
        }
    }

    if (args.size() == 1) {
        // Config file mode
        if (args[0] == "--help" || args[0] == "-h") {
            printUsage(argv[0]);
            return 0;
        }
        scenes = parseSceneConfigs(args[0]);
        if (scenes.empty()) {
            std::cerr << "No valid scenes found in config file: " << args[0] << std::endl;
            return 1;
        }
    } else if (args.size() == 2) {
        // Legacy mode: environment + placement as arguments
        SceneConfig sc;
        sc.name = "Default";
        sc.environmentData = args[0];
        sc.placementData = args[1];
        scenes.push_back(sc);
    } else {
        printUsage(argc > 0 ? argv[0] : "TrackingMinimalDemo");
        return 1;
    }

    if (!jsonMode) {
        std::cout << "Loaded " << scenes.size() << " scene(s):" << std::endl;
        for (size_t i = 0; i < scenes.size(); i++) {
            std::cout << "  [" << (i + 1) << "] " << scenes[i].name << std::endl;
        }
        std::cout << std::endl;
    } else {
        // JSON mode: disable ALL output buffering for pipe
        setvbuf(stdout, NULL, _IONBF, 0);  // C stdio: fully unbuffered
        std::cout.setf(std::ios::unitbuf);  // C++ stream: flush after every op
        std::cerr << "[JSON Mode] Loaded " << scenes.size() << " scene(s)" << std::endl;
    }

    // ---- Load SDK libraries ----
    #if defined(__linux__)
        Dl_info dlinfo;
        dladdr(reinterpret_cast<void*>(&main), &dlinfo);
        std::string path = getParentPath(dlinfo.dli_fname);
        std::string libNameADN = path + "/libAntilatencyDeviceNetwork.so";
        std::string libNameTracking = path + "/libAntilatencyAltTracking.so";
        std::string libNameEnvironmentSelector = path + "/libAntilatencyAltEnvironmentSelector.so";
        std::string libNameHW = path + "/libAntilatencyHardwareExtensionInterface.so";
    #else
        std::string libNameADN = "AntilatencyDeviceNetwork";
        std::string libNameTracking = "AntilatencyAltTracking";
        std::string libNameEnvironmentSelector = "AntilatencyAltEnvironmentSelector";
        std::string libNameHW = "AntilatencyHardwareExtensionInterface";
    #endif

    Antilatency::DeviceNetwork::ILibrary deviceNetworkLibrary = Antilatency::InterfaceContract::getLibraryInterface<Antilatency::DeviceNetwork::ILibrary>(libNameADN.c_str());
    if (deviceNetworkLibrary == nullptr) {
        std::cout << "Failed to get Antilatency Device Network Library" << std::endl;
        return 1;
    }

    Antilatency::Alt::Tracking::ILibrary altTrackingLibrary = Antilatency::InterfaceContract::getLibraryInterface<Antilatency::Alt::Tracking::ILibrary>(libNameTracking.c_str());
    if (altTrackingLibrary == nullptr) {
        std::cout << "Failed to get Antilatency Alt Tracking Library" << std::endl;
        return 1;
    }

    Antilatency::Alt::Environment::Selector::ILibrary environmentSelectorLibrary = Antilatency::InterfaceContract::getLibraryInterface<Antilatency::Alt::Environment::Selector::ILibrary>(libNameEnvironmentSelector.c_str());
    if (environmentSelectorLibrary == nullptr) {
        std::cout << "Failed to get Antilatency Alt Environment Selector Library" << std::endl;
        return 1;
    }

    Antilatency::HardwareExtensionInterface::ILibrary hwLibrary = Antilatency::InterfaceContract::getLibraryInterface<Antilatency::HardwareExtensionInterface::ILibrary>(libNameHW.c_str());
    if (hwLibrary == nullptr) {
        std::cout << "Failed to get Hardware Extension Interface Library" << std::endl;
        return 1;
    }

    // ---- Create device network ----
    Antilatency::DeviceNetwork::IDeviceFilter filter = deviceNetworkLibrary.createFilter();
    filter.addUsbDevice(Antilatency::DeviceNetwork::Constants::AllUsbDevices);
    Antilatency::DeviceNetwork::INetwork network = deviceNetworkLibrary.createNetwork(filter);
    if (network == nullptr) {
        std::cout << "Failed to create Antilatency Device Network" << std::endl;
        return 1;
    }
    if (!jsonMode) std::cout << "Antilatency Device Network created" << std::endl;

    // ---- Initialize first scene ----
    int currentSceneIndex = 0;
    Antilatency::Alt::Environment::IEnvironment currentEnvironment = environmentSelectorLibrary.createEnvironment(scenes[0].environmentData);
    if (currentEnvironment == nullptr) {
        std::cout << "Failed to create environment for scene: " << scenes[0].name << std::endl;
        return 1;
    }
    Antilatency::Math::floatP3Q currentPlacement = altTrackingLibrary.createPlacement(scenes[0].placementData);
    if (!jsonMode) std::cout << "Active scene: [1] " << scenes[0].name << std::endl;

    // ---- Cotask constructors ----
    Antilatency::Alt::Tracking::ITrackingCotaskConstructor altTrackingCotaskConstructor = altTrackingLibrary.createTrackingCotaskConstructor();
    if (altTrackingCotaskConstructor == nullptr) {
        std::cout << "Failed to create Alt Tracking Cotask Constructor" << std::endl;
        return 1;
    }

    Antilatency::HardwareExtensionInterface::ICotaskConstructor hwCotaskConstructor = hwLibrary.getCotaskConstructor();
    if (hwCotaskConstructor == nullptr) {
        std::cout << "Failed to create HW Extension Cotask Constructor" << std::endl;
        return 1;
    }

    // ---- State variables ----
    uint32_t prevUpdateId = 0;
    std::vector<TrackerInstance> trackers;
    int nextTrackerId = 1;

    std::vector<HWExtInstance> hwExtensions;
    bool io7State = false;  // Global IO7 toggle state (O key)

    // Input pins: IO1, IO2, IOA3, IOA4, IO5, IO6, IO8 (7 pins)
    // Output pin: IO7 (1 pin)
    const Antilatency::HardwareExtensionInterface::Interop::Pins inputPinDefs[] = {
        Antilatency::HardwareExtensionInterface::Interop::Pins::IO1,
        Antilatency::HardwareExtensionInterface::Interop::Pins::IO2,
        Antilatency::HardwareExtensionInterface::Interop::Pins::IOA3,
        Antilatency::HardwareExtensionInterface::Interop::Pins::IOA4,
        Antilatency::HardwareExtensionInterface::Interop::Pins::IO5,
        Antilatency::HardwareExtensionInterface::Interop::Pins::IO6,
        Antilatency::HardwareExtensionInterface::Interop::Pins::IO8
    };
    const int inputPinCount = 7;

    if (!jsonMode) std::cout << "Waiting for devices... (Press [L] list scenes, [1]-[9] switch, [A] IO7-A, [B] IO7-B, [C] IO8-B, [O] IO7-All, [Q] quit)" << std::endl;

    // ============================================================
    // Main loop
    // ============================================================
    bool running = true;
    while (running && network != nullptr) {
        // ---- Handle keyboard input ----
        int key = getKeyPress();
        if (key != -1) {
            if (key == 'q' || key == 'Q') {
                std::cout << "\nQuitting..." << std::endl;
                running = false;
                break;
            } else if (key == 'l' || key == 'L') {
                std::cout << "\n\nAvailable scenes:" << std::endl;
                for (size_t i = 0; i < scenes.size(); i++) {
                    std::cout << "  [" << (i + 1) << "] " << scenes[i].name;
                    if (static_cast<int>(i) == currentSceneIndex) std::cout << " (active)";
                    std::cout << std::endl;
                }
                std::cout << std::endl;
            } else if (key == 'a' || key == 'A') {
                for (auto& hw : hwExtensions) {
                    if (hw.type == "A" && hw.cotask != nullptr && !hw.cotask.isTaskFinished()) {
                        hw.io7State = !hw.io7State;
                        hw.outputPinIO7.setState(hw.io7State
                            ? Antilatency::HardwareExtensionInterface::Interop::PinState::High
                            : Antilatency::HardwareExtensionInterface::Interop::PinState::Low);
                        std::cout << "\n>> IO7[A]: " << (hw.io7State ? "ON" : "OFF") << std::endl;
                        break;
                    }
                }
            } else if (key == 'b' || key == 'B') {
                for (auto& hw : hwExtensions) {
                    if (hw.type == "B" && hw.cotask != nullptr && !hw.cotask.isTaskFinished()) {
                        hw.io7State = !hw.io7State;
                        hw.outputPinIO7.setState(hw.io7State
                            ? Antilatency::HardwareExtensionInterface::Interop::PinState::High
                            : Antilatency::HardwareExtensionInterface::Interop::PinState::Low);
                        std::cout << "\n>> IO7[B] (小震動): " << (hw.io7State ? "ON" : "OFF") << std::endl;
                        break;
                    }
                }
            } else if (key == 'c' || key == 'C') {
                for (auto& hw : hwExtensions) {
                    if (hw.type == "B" && hw.hasIO8Output && hw.cotask != nullptr && !hw.cotask.isTaskFinished()) {
                        hw.io8State = !hw.io8State;
                        hw.outputPinIO8.setState(hw.io8State
                            ? Antilatency::HardwareExtensionInterface::Interop::PinState::High
                            : Antilatency::HardwareExtensionInterface::Interop::PinState::Low);
                        std::cout << "\n>> IO8[B] (大震動): " << (hw.io8State ? "ON" : "OFF") << std::endl;
                        break;
                    }
                }
            } else if (key == 'o' || key == 'O') {
                if (!hwExtensions.empty()) {
                    io7State = !io7State;
                    for (auto& hw : hwExtensions) {
                        if (hw.cotask != nullptr && !hw.cotask.isTaskFinished()) {
                            hw.io7State = io7State;
                            hw.outputPinIO7.setState(io7State
                                ? Antilatency::HardwareExtensionInterface::Interop::PinState::High
                                : Antilatency::HardwareExtensionInterface::Interop::PinState::Low);
                        }
                    }
                    std::cout << "\n>> IO7 Output (all): " << (io7State ? "ON (High)" : "OFF (Low)") << std::endl;
                } else {
                    std::cout << "\n>> IO7: No Extension Modules connected" << std::endl;
                }
            } else if (key >= '1' && key <= '9') {
                int idx = key - '1';
                if (idx != currentSceneIndex && idx < static_cast<int>(scenes.size())) {
                    if (switchScene(idx, scenes, environmentSelectorLibrary, altTrackingLibrary,
                                    currentEnvironment, currentPlacement, trackers)) {
                        currentSceneIndex = idx;
                        nextTrackerId = 1;
                        prevUpdateId = 0; // Force device re-scan
                    }
                }
            }
        }

        const uint32_t currentUpdateId = network.getUpdateId();

        if (prevUpdateId != currentUpdateId) {
            prevUpdateId = currentUpdateId;

            // Remove finished tracker cotasks
            trackers.erase(
                std::remove_if(trackers.begin(), trackers.end(),
                    [](TrackerInstance& t) {
                        return t.cotask == nullptr || t.cotask.isTaskFinished();
                    }),
                trackers.end());

            // Collect nodes already in use
            std::vector<Antilatency::DeviceNetwork::NodeHandle> usedNodes;
            for (auto& t : trackers) {
                usedNodes.push_back(t.node);
            }

            // Find and start ALL idle tracking nodes
            // Tag B (主射手頭盔震動器) and D (對講機) are IO-only — skip Alt Tracker for them
            auto idleNodes = getAllIdleTrackingNodes(network, altTrackingCotaskConstructor);
            for (auto node : idleNodes) {
                // Skip if already tracked
                bool alreadyUsed = false;
                for (auto& used : usedNodes) {
                    if (used == node) { alreadyUsed = true; break; }
                }
                if (alreadyUsed) continue;

                // Skip IO-only devices (Tag B, D) — no Alt Tracker needed
                std::string nodeType = getNodeType(network, node);
                if (nodeType == "B" || nodeType == "D") continue;

                auto cotask = altTrackingCotaskConstructor.startTask(network, node, currentEnvironment);
                if (cotask != nullptr) {
                    TrackerInstance ti;
                    ti.node = node;
                    ti.cotask = cotask;
                    ti.id = nextTrackerId++;
                    ti.type = getNodeType(network, node);
                    ti.number = getNodeNumber(network, node);
                    trackers.push_back(ti);
                    
                    if (!jsonMode) {
                        std::cout << "\nAlt Tracker #" << ti.id;
                        if (!ti.number.empty()) std::cout << " Number:" << ti.number;
                        if (!ti.type.empty()) std::cout << " [" << ti.type << "]";
                        std::cout << " connected!" << std::endl;
                    } else {
                        std::cerr << "[JSON] Tracker #" << ti.id << " connected" << std::endl;
                    }
                }
            }

            // HW extensions (multi-instance): remove finished ones
            hwExtensions.erase(
                std::remove_if(hwExtensions.begin(), hwExtensions.end(),
                    [](HWExtInstance& hw) {
                        return hw.cotask == nullptr || hw.cotask.isTaskFinished();
                    }),
                hwExtensions.end());

            // Collect HW nodes already in use
            std::vector<Antilatency::DeviceNetwork::NodeHandle> usedHWNodes;
            for (auto& hw : hwExtensions) {
                usedHWNodes.push_back(hw.node);
            }

            // Find and start ALL idle HW Extension nodes
            auto idleHWNodes = getAllIdleExtensionNodes(network, hwCotaskConstructor);
            for (auto hwNode : idleHWNodes) {
                // Skip if already in use
                bool alreadyUsed = false;
                for (auto& used : usedHWNodes) {
                    if (used == hwNode) { alreadyUsed = true; break; }
                }
                if (alreadyUsed) continue;

                // Tag E (副射手頭盔) and F (主射手頭盔定位) are Alt-only — no HW Extension needed
                std::string hwNodeType = getNodeType(network, hwNode);
                if (hwNodeType == "E" || hwNodeType == "F") continue;

                auto cotask = hwCotaskConstructor.startTask(network, hwNode);
                if (cotask != nullptr) {
                    HWExtInstance hw;
                    hw.node = hwNode;
                    hw.cotask = cotask;
                    hw.type = hwNodeType;

                    // Per-type pin configuration:
                    // Tag B (IO-only): 6 input (IO1-IO6) + 2 output (IO7 小震動, IO8 大震動) = 8 pins
                    //   No Alt Tracker on Tag B, so 2 output pins are safe
                    // Others (A/C/D): 7 input (IO1-IO6, IO8) + 1 output (IO7) = 8 pins
                    if (hw.type == "B") {
                        // 6 input pins: IO1, IO2, IOA3, IOA4, IO5, IO6
                        for (int i = 0; i < 6; i++) {
                            hw.inputPins.push_back(cotask.createInputPin(inputPinDefs[i]));
                        }
                        // IO7 output (小震動)
                        hw.outputPinIO7 = cotask.createOutputPin(
                            Antilatency::HardwareExtensionInterface::Interop::Pins::IO7,
                            Antilatency::HardwareExtensionInterface::Interop::PinState::Low);
                        hw.io7State = false;
                        // IO8 output (大震動)
                        hw.outputPinIO8 = cotask.createOutputPin(
                            Antilatency::HardwareExtensionInterface::Interop::Pins::IO8,
                            Antilatency::HardwareExtensionInterface::Interop::PinState::Low);
                        hw.io8State = false;
                        hw.hasIO8Output = true;
                    } else {
                        for (int i = 0; i < inputPinCount; i++) {
                            hw.inputPins.push_back(cotask.createInputPin(inputPinDefs[i]));
                        }
                        hw.outputPinIO7 = cotask.createOutputPin(
                            Antilatency::HardwareExtensionInterface::Interop::Pins::IO7,
                            Antilatency::HardwareExtensionInterface::Interop::PinState::Low);
                        hw.io7State = false;
                        hw.hasIO8Output = false;
                    }

                    cotask.run();
                    hwExtensions.push_back(hw);

                    if (!jsonMode) {
                        std::cout << "\nExtension Module";
                        if (!hw.type.empty()) std::cout << " [" << hw.type << "]";
                        if (hw.hasIO8Output)
                            std::cout << " connected! (6 input + IO7/IO8 output, IO-only)" << std::endl;
                        else
                            std::cout << " connected! (7 input + IO7 output)" << std::endl;
                    } else {
                        std::cerr << "[JSON] Extension Module";
                        if (!hw.type.empty()) std::cerr << " [" << hw.type << "]";
                        std::cerr << " connected" << std::endl;
                    }
                }
            }
        }

        // ---- Read and display data ----
        bool hasAnyTracker = false;
        for (auto& t : trackers) {
            if (t.cotask != nullptr && !t.cotask.isTaskFinished()) {
                hasAnyTracker = true;
                break;
            }
        }
        // Build map of type -> HWExtInstance for pairing
        std::map<std::string, HWExtInstance*> hwByType;
        for (auto& hw : hwExtensions) {
            if (hw.cotask != nullptr && !hw.cotask.isTaskFinished() && !hw.type.empty()) {
                hwByType[hw.type] = &hw;
            }
        }
        bool hasIO = !hwByType.empty();

        if (hasAnyTracker || hasIO) {
            std::ostringstream oss;
            oss << std::fixed << std::setprecision(4);

            // Scene indicator
            oss << "[S" << (currentSceneIndex + 1) << "] ";

            // Display data for each tracker (with per-tracker IO)
            if (hasAnyTracker) {
                for (auto& t : trackers) {
                    if (t.cotask == nullptr || t.cotask.isTaskFinished()) continue;
                    Antilatency::Alt::Tracking::State state = t.cotask.getExtrapolatedState(currentPlacement, 0.005f);
                    std::string tag = typeToTag(t.type);
                    if (!tag.empty()) {
                        oss << "T" << t.id << "[" << tag << "]";
                    } else if (!t.number.empty()) {
                        oss << "#" << t.number;
                    } else {
                        oss << "T" << t.id;
                    }
                    oss << ":"
                        << "P("
                        << std::setw(7) << state.pose.position.x << ","
                        << std::setw(7) << state.pose.position.y << ","
                        << std::setw(7) << state.pose.position.z << ") "
                        << "R("
                        << std::setw(7) << state.pose.rotation.x << ","
                        << std::setw(7) << state.pose.rotation.y << ","
                        << std::setw(7) << state.pose.rotation.z << ","
                        << std::setw(7) << state.pose.rotation.w << ") "
                        << "S:" << static_cast<int32_t>(state.stability.stage);

                    // Show paired IO for this tracker
                    auto hwIt = hwByType.find(t.type);
                    if (hwIt != hwByType.end()) {
                        auto& hw = *(hwIt->second);
                        oss << " IO[" << tag << "]:";
                        // First 6 input pins: IO1, IO2, IOA3, IOA4, IO5, IO6
                        for (int i = 0; i < 6; i++) {
                            auto pinState = hw.inputPins[i].getState();
                            oss << ((pinState == Antilatency::HardwareExtensionInterface::Interop::PinState::Low) ? "1" : "0");
                        }
                        // IO7 output bit
                        oss << (hw.io7State ? "1" : "0");
                        // IO8: output for Tag B, input for others
                        if (hw.hasIO8Output) {
                            oss << (hw.io8State ? "1" : "0");
                        } else {
                            auto pin8State = hw.inputPins[6].getState();  // 7th input pin = IO8
                            oss << ((pin8State == Antilatency::HardwareExtensionInterface::Interop::PinState::Low) ? "1" : "0");
                        }
                    }
                    oss << "  ";
                }
            } else {
                oss << "Tracker: --  ";
            }

            // Display IO-only devices (Tag B, D — no Alt Tracker)
            for (auto& hw : hwExtensions) {
                if (hw.cotask == nullptr || hw.cotask.isTaskFinished()) continue;
                if (hw.type != "B" && hw.type != "D") continue;  // Only IO-only types
                oss << "IO[" << hw.type << "]:";
                for (size_t i = 0; i < hw.inputPins.size(); i++) {
                    auto pinState = hw.inputPins[i].getState();
                    oss << ((pinState == Antilatency::HardwareExtensionInterface::Interop::PinState::Low) ? "1" : "0");
                }
                oss << (hw.io7State ? "1" : "0");
                if (hw.hasIO8Output) {
                    oss << (hw.io8State ? "1" : "0");
                }
                oss << "  ";
            }

            if (!hasIO) {
                oss << "IO: --";
            }

            // ---- Build JSON ----
            std::ostringstream js;
            js << std::fixed << std::setprecision(6);
            js << "{";
            js << "\"scene\":" << (currentSceneIndex + 1) << ",";
            js << "\"sceneName\":\"" << scenes[currentSceneIndex].name << "\",";

            // Trackers array (with per-tracker IO)
            // Trackers array (with per-tracker IO)
            js << "\"trackers\":[";
            bool firstTracker = true;
            // Tracked devices (A, C — with Alt Tracker position data)
            if (hasAnyTracker) {
                for (auto& t : trackers) {
                    if (t.cotask == nullptr || t.cotask.isTaskFinished()) continue;
                    Antilatency::Alt::Tracking::State state = t.cotask.getExtrapolatedState(currentPlacement, 0.005f);
                    if (!firstTracker) js << ",";
                    firstTracker = false;

                    std::string tag = typeToTag(t.type);

                    // Build per-tracker IO 8-bit string: IO1,IO2,IOA3,IOA4,IO5,IO6,IO7(out),IO8
                    std::string ioBits = "00000000";
                    auto hwIt = hwByType.find(t.type);
                    if (hwIt != hwByType.end()) {
                        auto& hw = *(hwIt->second);
                        for (int i = 0; i < 6; i++) {
                            auto pinState = hw.inputPins[i].getState();
                            ioBits[i] = (pinState == Antilatency::HardwareExtensionInterface::Interop::PinState::Low) ? '1' : '0';
                        }
                        ioBits[6] = hw.io7State ? '1' : '0';
                        if (hw.hasIO8Output) {
                            ioBits[7] = hw.io8State ? '1' : '0';
                        } else {
                            auto pin8State = hw.inputPins[6].getState();  // 7th input pin = IO8
                            ioBits[7] = (pin8State == Antilatency::HardwareExtensionInterface::Interop::PinState::Low) ? '1' : '0';
                        }
                    }

                    js << "{\"id\":" << t.id
                       << ",\"tag\":\"" << tag << "\""
                       << ",\"type\":\"" << t.type << "\""
                       << ",\"number\":\"" << t.number << "\""
                       << ",\"px\":" << state.pose.position.x
                       << ",\"py\":" << state.pose.position.y
                       << ",\"pz\":" << state.pose.position.z
                       << ",\"rx\":" << state.pose.rotation.x
                       << ",\"ry\":" << state.pose.rotation.y
                       << ",\"rz\":" << state.pose.rotation.z
                       << ",\"rw\":" << state.pose.rotation.w
                       << ",\"stability\":" << static_cast<int32_t>(state.stability.stage)
                       << ",\"io\":\"" << ioBits << "\""
                       << "}";
                }
            }
            // IO-only devices (B, D — no Alt Tracker, IO only)
            for (auto& hw : hwExtensions) {
                if (hw.cotask == nullptr || hw.cotask.isTaskFinished()) continue;
                if (hw.type != "B" && hw.type != "D") continue;
                if (!firstTracker) js << ",";
                firstTracker = false;

                std::string ioBits = "00000000";
                for (size_t i = 0; i < hw.inputPins.size() && i < 6; i++) {
                    auto pinState = hw.inputPins[i].getState();
                    ioBits[i] = (pinState == Antilatency::HardwareExtensionInterface::Interop::PinState::Low) ? '1' : '0';
                }
                ioBits[6] = hw.io7State ? '1' : '0';
                if (hw.hasIO8Output) {
                    ioBits[7] = hw.io8State ? '1' : '0';
                } else {
                    if (hw.inputPins.size() > 6) {
                        auto pin8State = hw.inputPins[6].getState();
                        ioBits[7] = (pin8State == Antilatency::HardwareExtensionInterface::Interop::PinState::Low) ? '1' : '0';
                    }
                }

                // IO-only: id=0, stability=0, position=0, rw=1
                js << "{\"id\":0"
                   << ",\"tag\":\"" << hw.type << "\""
                   << ",\"type\":\"" << hw.type << "\""
                   << ",\"number\":\"\""
                   << ",\"px\":0,\"py\":0,\"pz\":0"
                   << ",\"rx\":0,\"ry\":0,\"rz\":0,\"rw\":1"
                   << ",\"stability\":0"
                   << ",\"io\":\"" << ioBits << "\""
                   << "}";
            }
            js << "],";

            // Global IO state (backwards compatible for monitor/viewer)
            js << "\"io\":{\"connected\":" << (hasIO ? "true" : "false");
            if (hasIO) {
                auto& firstHW = hwExtensions[0];
                js << ",\"type\":\"" << firstHW.type << "\"";
                js << ",\"inputs\":[";
                for (size_t i = 0; i < firstHW.inputPins.size(); i++) {
                    if (i > 0) js << ",";
                    auto pinState = firstHW.inputPins[i].getState();
                    js << ((pinState == Antilatency::HardwareExtensionInterface::Interop::PinState::Low) ? 1 : 0);
                }
                js << "]";
                js << ",\"io7out\":" << (firstHW.io7State ? "true" : "false");
            }
            js << "}";
            js << "}";

            if (jsonMode) {
                // --json 模式：只輸出 JSON 到 stdout (一行一筆，供 pipe 使用)
                std::cout << js.str() << std::endl;
            } else {
                // 正常模式：輸出文字到 console + 寫入檔案
                std::string line = oss.str();
                if (line.size() < 160) line.resize(160, ' ');
                std::cout << "\r" << line << std::flush;

                // Atomic write to file
                std::ofstream jsonFile("tracking_data.json.tmp");
                if (jsonFile.is_open()) {
                    jsonFile << js.str();
                    jsonFile.close();
                    try {
                        std::filesystem::rename("tracking_data.json.tmp", "tracking_data.json");
                    } catch (...) {
                        std::filesystem::copy_file("tracking_data.json.tmp", "tracking_data.json",
                            std::filesystem::copy_options::overwrite_existing);
                        std::filesystem::remove("tracking_data.json.tmp");
                    }
                }
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(2)); // 500Hz - Alt IMU high-speed sampling
    }

    // Cleanup
    for (auto& t : trackers) {
        t.cotask = nullptr;
    }
    trackers.clear();
    for (auto& hw : hwExtensions) {
        hw.cotask = nullptr;
    }
    hwExtensions.clear();

    return 0;
}
