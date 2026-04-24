#include <iostream>
#include <thread>
#include <chrono>
#include <string>
#include <fstream> // NEW: For CSV logging

// --- 1. BIOGEARS HEADERS (Must come before Windows headers) ---
#include <biogears/engine/BioGearsPhysiologyEngine.h>
#include <biogears/cdm/system/physiology/SECardiovascularSystem.h>
#include <biogears/cdm/system/physiology/SEBloodChemistrySystem.h>

// Launch Patient Actions (+3Gz)
#include <biogears/cdm/patient/actions/SEHemorrhage.h>             // Blood pooling / Fluid Loss
#include <biogears/cdm/patient/actions/SEAcuteRespiratoryDistress.h> // Chest compression
#include <biogears/cdm/patient/actions/SEAcuteStress.h>           // Sympathetic nervous response

// Property Units
#include <biogears/cdm/properties/SEScalarVolumePerTime.h>
#include <biogears/cdm/properties/SEScalar0To1.h>
#include <biogears/cdm/properties/SEScalarVolume.h>

// --- 2. WINDOWS NETWORKING (Must come after BioGears) ---
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")

using namespace biogears;

int main() {
    // --- NETWORKING SETUP ---
    WSADATA wsaData; WSAStartup(MAKEWORD(2, 2), &wsaData);
    SOCKET udpSocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    sockaddr_in serverAddress;
    serverAddress.sin_family = AF_INET;
    serverAddress.sin_port = htons(8080);
    inet_pton(AF_INET, "127.0.0.1", &serverAddress.sin_addr);

    // --- NEW: CREATE THE CSV LOG FILE ---
    std::ofstream csvFile("Flight_Telemetry.csv");
    // Write the column headers. The "Phase" column will track our events!
    csvFile << "Time(s),HeartRate(BPM),StrokeVolume(mL),SpO2(%),MissionPhase\n";

    // --- ENGINE SETUP ---
    std::unique_ptr<PhysiologyEngine> bg = CreateBioGearsEngine("Aerospace_DigitalTwin.log");
    bg->LoadState("C:/Program Files/BioGears/bin/states/StandardMale@0s.xml");

    // --- ACTION SETUP ---
    SEHemorrhage legBleed;
    legBleed.SetCompartment("LeftLeg");
    SEAcuteRespiratoryDistress chestCompression;
    SEAcuteStress sympatheticResponse;
    SEHemorrhage spaceDiuresis;
    spaceDiuresis.SetCompartment("VenaCava");

    double totalTime = 0.0;
    double timeStep  = 0.1;
    
    // We will use this string to label the graph events in the CSV
    std::string currentPhase = "1_Pad_1G"; 

    std::cout << "Engine Ready. Systems Green for Launch..." << std::endl;

    while (true) {
        bg->AdvanceModelTime(timeStep, TimeUnit::s);
        totalTime += timeStep;

        // =====================================================
        //   PHASE 2: ASCENT / +3Gz STRESS (T=30s to T=90s)
        // =====================================================
        if (totalTime > 30.0 && totalTime < 30.1) {
            std::cout << "\n[FLIGHT T+30s] IGNITION: +Gz stress beginning..." << std::endl;
            currentPhase = "2_Ascent_3G"; // Update CSV marker

            legBleed.GetInitialRate().SetValue(300.0, VolumePerTimeUnit::mL_Per_min);
            bg->ProcessAction(legBleed);
            chestCompression.GetSeverity().SetValue(0.7);
            bg->ProcessAction(chestCompression);
            sympatheticResponse.GetSeverity().SetValue(1.0);
            bg->ProcessAction(sympatheticResponse);
        }
        // =====================================================
        //   PHASE 3: ARRIVAL IN ORBIT (T=90s to T=120s)
        // =====================================================
        else if (totalTime > 90.0 && totalTime < 90.1) {
            std::cout << "\n[FLIGHT T+90s] MECO: Zero-G. Launch stresses cleared." << std::endl;
            currentPhase = "3_Orbit_Arrival"; // Update CSV marker

            legBleed.GetInitialRate().SetValue(0.0, VolumePerTimeUnit::mL_Per_min);
            bg->ProcessAction(legBleed);
            chestCompression.GetSeverity().SetValue(0.0);
            bg->ProcessAction(chestCompression);
            sympatheticResponse.GetSeverity().SetValue(0.0);
            bg->ProcessAction(sympatheticResponse);
        }
        // =====================================================
        //   PHASE 4: LONG-TERM ADAPTATION (T=120s+)
        // =====================================================
        else if (totalTime > 120.0 && totalTime < 120.1) {
            std::cout << "\n[ORBIT T+120s] FAST-FORWARD: Inducing Long-Term Space Adaptation." << std::endl;
            currentPhase = "4_LongTerm_Adaptation"; // Update CSV marker

            sympatheticResponse.GetSeverity().SetValue(0.2); 
            bg->ProcessAction(sympatheticResponse);
            spaceDiuresis.GetInitialRate().SetValue(50.0, VolumePerTimeUnit::mL_Per_min); 
            bg->ProcessAction(spaceDiuresis);
        }

        // --- TELEMETRY EXTRACTION ---
        double hr   = bg->GetCardiovascularSystem()->GetHeartRate(FrequencyUnit::Per_min);
        double co   = bg->GetCardiovascularSystem()->GetCardiacOutput(VolumePerTimeUnit::L_Per_min);
        double sv   = (hr > 0.0) ? (co / hr) * 1000.0 : 0.0;
        double spo2 = bg->GetBloodChemistrySystem()->GetOxygenSaturation();

        // --- NEW: WRITE TO CSV ---
        csvFile << totalTime << "," << hr << "," << sv << "," << (spo2 * 100.0) << "," << currentPhase << "\n";

        // --- JSON PACKAGING & UDP BROADCAST ---
        std::string payload = "{\"HR\":"   + std::to_string(hr)   +
                              ",\"SV\":"   + std::to_string(sv)   +
                              ",\"SPO2\":" + std::to_string(spo2) + "}";

        sendto(udpSocket, payload.c_str(), (int)payload.length(), 0,
               (SOCKADDR*)&serverAddress, sizeof(serverAddress));

        // --- CONSOLE OUTPUT ---
        std::cout << "T+" << (int)totalTime << "s | HR: " << (int)hr
                  << " | SV: " << (int)sv
                  << " | SpO2: " << (int)(spo2 * 100) << "%" << std::endl;

        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    return 0;
}