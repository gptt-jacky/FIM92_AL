//Reproduction test: 2 HW Extension output pins + Alt Tracking cotask on same device
//Last updated: 2026/04/29
//
//Default mode : 10-second text diagnostic, prints CONFIRMED FAIL / PASS verdict
//--json mode  : continuous JSON output (same format as main program) for monitor.py pipe

#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>
#include <fstream>
#include <thread>
#include <chrono>

#include <Antilatency.InterfaceContract.LibraryLoader.h>
#include <Antilatency.DeviceNetwork.h>
#include <Antilatency.Alt.Tracking.h>
#include <Antilatency.Alt.Environment.Selector.h>
#include <Antilatency.HardwareExtensionInterface.h>
#include <Antilatency.HardwareExtensionInterface.Interop.h>

using Pins     = Antilatency::HardwareExtensionInterface::Interop::Pins;
using PinState = Antilatency::HardwareExtensionInterface::Interop::PinState;

// ---- Simple JSON parser: extract first environmentData from scenes.json ----
static std::string extractJsonValue(const std::string& json, const std::string& key) {
    std::string search = "\"" + key + "\"";
    auto pos = json.find(search);
    if (pos == std::string::npos) return "";
    pos = json.find(':', pos + search.size());
    if (pos == std::string::npos) return "";
    pos++;
    while (pos < json.size() && (json[pos]==' '||json[pos]=='\t'||json[pos]=='\n'||json[pos]=='\r')) pos++;
    if (pos >= json.size()) return "";
    if (json[pos] == '"') {
        auto end = json.find('"', pos + 1);
        if (end == std::string::npos) return "";
        return json.substr(pos + 1, end - pos - 1);
    }
    auto end = json.find_first_of(",}\n\r", pos);
    return json.substr(pos, end - pos);
}

static std::string loadFirstEnvironment(const std::string& path) {
    std::ifstream f(path);
    if (!f.is_open()) return "";
    std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    auto arrStart = content.find('[');
    auto arrEnd   = content.rfind(']');
    if (arrStart == std::string::npos || arrEnd == std::string::npos) return "";
    std::string arr = content.substr(arrStart + 1, arrEnd - arrStart - 1);
    auto objStart = arr.find('{');
    auto objEnd   = arr.find('}', objStart);
    if (objStart == std::string::npos || objEnd == std::string::npos) return "";
    return extractJsonValue(arr.substr(objStart, objEnd - objStart + 1), "environmentData");
}

// ---- Build JSON line for monitor.py ----
static std::string buildJson(int stability, float px, float py, float pz,
                              float rx, float ry, float rz, float rw,
                              const std::string& ioBits, bool hwConnected)
{
    std::ostringstream js;
    js << std::fixed << std::setprecision(6);
    js << "{\"scene\":1,\"sceneName\":\"ReproductionTest\",";
    js << "\"trackers\":[{";
    js << "\"id\":1,\"tag\":\"TEST\",\"type\":\"TEST\",\"number\":\"\",";
    js << "\"px\":" << px << ",\"py\":" << py << ",\"pz\":" << pz << ",";
    js << "\"rx\":" << rx << ",\"ry\":" << ry << ",\"rz\":" << rz << ",\"rw\":" << rw << ",";
    js << "\"stability\":" << stability << ",";
    js << "\"io\":\"" << ioBits << "\"";
    js << "}],";
    js << "\"io\":{\"connected\":" << (hwConnected ? "true" : "false");
    if (hwConnected) {
        js << ",\"type\":\"TEST\"";
        // inputs[]: IO1 IO2 IOA3 IOA4 IO5 IO6 IO8(index6)
        js << ",\"inputs\":[";
        for (int i = 0; i < 6; i++) {
            if (i > 0) js << ",";
            js << (ioBits[i] == '1' ? 1 : 0);
        }
        js << ",0]";  // IO8 is output in this test - report as 0
        js << ",\"io7out\":false";  // IO7 output kept Low throughout test
    }
    js << "}}";
    return js.str();
}

// ============================================================
// MAIN
// ============================================================
int main(int argc, char* argv[]) {

    // ---- Parse arguments ----
    bool jsonMode = false;
    std::string scenesFile = "scenes.json";

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--json" || arg == "-j") {
            jsonMode = true;
        } else {
            scenesFile = arg;
        }
    }

    if (jsonMode) {
        setvbuf(stdout, NULL, _IONBF, 0);
        std::cout.setf(std::ios::unitbuf);
    } else {
        std::cout << "========================================================" << std::endl;
        std::cout << " Reproduction Test: 2 Output Pins + Alt Tracker Conflict" << std::endl;
        std::cout << " Antilatency SDK 4.5.0" << std::endl;
        std::cout << "========================================================" << std::endl;
        std::cout << std::endl;
        std::cout << "Config:" << std::endl;
        std::cout << "  HW Extension : 6 input (IO1-IO6) + IO7 output + IO8 output" << std::endl;
        std::cout << "  Alt Tracker  : same physical device node" << std::endl;
        std::cout << "Expected: stability stays 0 (LED never turns green)" << std::endl;
        std::cout << std::endl;
    }

    // ---- Load environmentData from scenes.json ----
    std::string envData = loadFirstEnvironment(scenesFile);
    if (envData.empty()) {
        std::cerr << "[FAIL] Cannot load environmentData from: " << scenesFile << std::endl;
        return 1;
    }
    std::cerr << "[INFO] Environment loaded from: " << scenesFile << std::endl;

    // ---- Load SDK libraries ----
    auto deviceNetworkLib = Antilatency::InterfaceContract::getLibraryInterface<
        Antilatency::DeviceNetwork::ILibrary>("AntilatencyDeviceNetwork");
    auto altLib = Antilatency::InterfaceContract::getLibraryInterface<
        Antilatency::Alt::Tracking::ILibrary>("AntilatencyAltTracking");
    auto envLib = Antilatency::InterfaceContract::getLibraryInterface<
        Antilatency::Alt::Environment::Selector::ILibrary>("AntilatencyAltEnvironmentSelector");
    auto hwLib = Antilatency::InterfaceContract::getLibraryInterface<
        Antilatency::HardwareExtensionInterface::ILibrary>("AntilatencyHardwareExtensionInterface");

    if (!deviceNetworkLib || !altLib || !envLib || !hwLib) {
        std::cerr << "[FAIL] Could not load SDK libraries" << std::endl;
        return 1;
    }

    // ---- Create device network ----
    auto filter = deviceNetworkLib.createFilter();
    filter.addUsbDevice(Antilatency::DeviceNetwork::Constants::AllUsbDevices);
    auto network = deviceNetworkLib.createNetwork(filter);
    if (!network) {
        std::cerr << "[FAIL] Could not create device network" << std::endl;
        return 1;
    }

    // ---- Create environment ----
    auto env = envLib.createEnvironment(envData);
    if (!env) {
        std::cerr << "[FAIL] Could not create environment" << std::endl;
        return 1;
    }
    auto placement = altLib.createPlacement("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA");

    auto altConstructor = altLib.createTrackingCotaskConstructor();
    auto hwConstructor  = hwLib.getCotaskConstructor();

    // ---- Find device with BOTH Alt Tracking AND HW Extension ----
    // Alt Tracking and HW Extension use DIFFERENT node handles on the same physical Socket.
    // Match them by comparing their parent nodes (same parent = same physical device).
    std::cerr << "[INFO] Searching for device (up to 10s)..." << std::endl;

    Antilatency::DeviceNetwork::NodeHandle altTargetNode =
        Antilatency::DeviceNetwork::NodeHandle::Null;
    Antilatency::DeviceNetwork::NodeHandle hwTargetNode =
        Antilatency::DeviceNetwork::NodeHandle::Null;
    uint32_t prevUpdateId = 0;

    for (int attempt = 0; attempt < 50; attempt++) {
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
        uint32_t uid = network.getUpdateId();
        if (uid == prevUpdateId) continue;
        prevUpdateId = uid;

        auto altNodes = altConstructor.findSupportedNodes(network);
        auto hwNodes  = hwConstructor.findSupportedNodes(network);

        for (auto& an : altNodes) {
            if (network.nodeGetStatus(an) != Antilatency::DeviceNetwork::NodeStatus::Idle) continue;
            auto parentA = network.nodeGetParent(an);

            for (auto& hn : hwNodes) {
                if (network.nodeGetStatus(hn) != Antilatency::DeviceNetwork::NodeStatus::Idle) continue;
                auto parentH = network.nodeGetParent(hn);

                if (parentA == parentH) {
                    altTargetNode = an;
                    hwTargetNode  = hn;
                    break;
                }
            }
            if (altTargetNode != Antilatency::DeviceNetwork::NodeHandle::Null) break;
        }
        if (altTargetNode != Antilatency::DeviceNetwork::NodeHandle::Null) break;
    }

    if (altTargetNode == Antilatency::DeviceNetwork::NodeHandle::Null) {
        std::cerr << "[FAIL] No device found with both Alt Tracking and HW Extension" << std::endl;
        return 1;
    }
    std::cerr << "[INFO] Device found (Alt node and HW node share same parent)" << std::endl;

    // ============================================================
    // STEP 1 - HW Extension: 6 input + IO7 output + IO8 output
    // ============================================================
    std::cerr << "[STEP 1] HW Extension cotask: 6 input + IO7 + IO8 output..." << std::endl;

    auto hwCotask = hwConstructor.startTask(network, hwTargetNode);
    if (!hwCotask) {
        std::cerr << "[FAIL] hwConstructor.startTask() returned null" << std::endl;
        return 1;
    }

    std::vector<Antilatency::HardwareExtensionInterface::IInputPin> inputPins;
    inputPins.push_back(hwCotask.createInputPin(Pins::IO1));
    inputPins.push_back(hwCotask.createInputPin(Pins::IO2));
    inputPins.push_back(hwCotask.createInputPin(Pins::IOA3));
    inputPins.push_back(hwCotask.createInputPin(Pins::IOA4));
    inputPins.push_back(hwCotask.createInputPin(Pins::IO5));
    inputPins.push_back(hwCotask.createInputPin(Pins::IO6));
    hwCotask.createOutputPin(Pins::IO7, PinState::Low);  // output 1
    hwCotask.createOutputPin(Pins::IO8, PinState::Low);  // output 2
    hwCotask.run();

    std::cerr << "[OK] HW Extension started" << std::endl;

    // ============================================================
    // STEP 2 - Alt Tracking on the SAME node
    // ============================================================
    std::cerr << "[STEP 2] Alt Tracking cotask on the SAME device node..." << std::endl;

    auto altCotask = altConstructor.startTask(network, altTargetNode, env);

    if (!altCotask) {
        std::cerr << "[RESULT] *** CONFIRMED FAIL *** - altCotask is null" << std::endl;
        if (!jsonMode) {
            std::cout << std::endl;
            std::cout << "[RESULT] *** CONFIRMED FAIL ***" << std::endl;
            std::cout << "  altConstructor.startTask() returned null immediately" << std::endl;
        }
        return 0;
    }

    std::cerr << "[INFO] altCotask non-null - observing..." << std::endl;
    if (!jsonMode) {
        std::cout << "[INFO] altCotask non-null, monitoring 10 seconds..." << std::endl;
        std::cout << "[INFO] Watch LED: should NOT turn green if issue is present" << std::endl;
        std::cout << std::endl;
    }

    // ============================================================
    // MAIN LOOP
    // ============================================================
    int maxStability = 0;

    for (int tick = 1; ; tick++) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        int elapsed_ms = tick * 100;

        bool altDead = altCotask.isTaskFinished();
        bool hwDead  = hwCotask.isTaskFinished();

        // Read Alt Tracker state
        int   stability = 0;
        float px = 0, py = 0, pz = 0;
        float rx = 0, ry = 0, rz = 0, rw = 1;

        if (!altDead) {
            auto state = altCotask.getExtrapolatedState(placement, 0.0f);
            stability = static_cast<int>(state.stability.stage);
            px = state.pose.position.x;
            py = state.pose.position.y;
            pz = state.pose.position.z;
            rx = state.pose.rotation.x;
            ry = state.pose.rotation.y;
            rz = state.pose.rotation.z;
            rw = state.pose.rotation.w;
        }
        if (stability > maxStability) maxStability = stability;

        // Read HW Extension IO
        std::string ioBits = "00000000";
        if (!hwDead && static_cast<int>(inputPins.size()) >= 6) {
            for (int i = 0; i < 6; i++) {
                ioBits[i] = (inputPins[i].getState() == PinState::Low) ? '1' : '0';
            }
            // IO7(bit6) and IO8(bit7) are outputs kept Low - display as 0
        }

        // ---- JSON mode ----
        if (jsonMode) {
            std::cout << buildJson(stability, px, py, pz, rx, ry, rz, rw,
                                   ioBits, !hwDead) << std::endl;
            if (altDead) {
                std::cerr << "[RESULT] *** CONFIRMED FAIL *** altCotask died at t="
                          << elapsed_ms << "ms" << std::endl;
                // Keep HW Extension running so monitor stays visible
                while (!hwCotask.isTaskFinished()) {
                    std::this_thread::sleep_for(std::chrono::milliseconds(100));
                    std::cout << buildJson(0, 0, 0, 0, 0, 0, 0, 1, "00000000", false)
                              << std::endl;
                }
                break;
            }
            continue;
        }

        // ---- Text mode ----
        if (altDead) {
            std::cout << std::endl;
            std::cout << "[RESULT] *** CONFIRMED FAIL *** altCotask died at t="
                      << elapsed_ms << "ms" << std::endl;
            break;
        }

        std::cout << "\r  t=" << std::setw(5) << elapsed_ms << "ms  "
                  << "stability=" << stability
                  << "  max=" << maxStability << "    " << std::flush;

        // Text mode stops after 10 seconds
        if (elapsed_ms >= 10000) {
            std::cout << std::endl << std::endl;
            std::cout << "--------------------------------------------------------" << std::endl;
            if (maxStability == 0) {
                std::cout << "[RESULT] *** CONFIRMED FAIL ***" << std::endl;
                std::cout << "  stability stayed 0 (InertialDataInitialization) for 10s" << std::endl;
                std::cout << "  LED never turned green - Alt Tracker silently non-functional" << std::endl;
            } else if (maxStability == 1) {
                std::cout << "[RESULT] PARTIAL FAIL - max stability=1 (3DOF only, no 6DOF)" << std::endl;
            } else {
                std::cout << "[RESULT] UNEXPECTED - stability reached " << maxStability << std::endl;
            }
            std::cout << "--------------------------------------------------------" << std::endl;
            break;
        }
    }

    return 0;
}
