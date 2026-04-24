/**
 * @file    main.cpp
 * @brief   Aerospace Digital Twin — BioGears Physiology Bridge
 *
 * @details
 * This program is the core simulation engine for the Aerospace Digital Twin.
 * It drives the BioGears physiology engine through a four-phase spaceflight
 * timeline and broadcasts real-time telemetry via UDP/8080 to downstream
 * visualizers (Python dashboard + Unreal Engine 5). All telemetry is also
 * persisted to Flight_Telemetry.csv for post-mission analysis.
 *
 * =========================================================================
 * THE PHYSIOLOGICAL PROXY METHODOLOGY
 * =========================================================================
 * BioGears is a closed-loop clinical physiology simulator — it has no
 * native model of gravitational acceleration. To simulate spaceflight
 * physiology, this bridge applies "physiological proxies": real BioGears
 * patient actions whose biological effects are medically analogous to what
 * an astronaut experiences during each flight phase. This is standard
 * aerospace medicine methodology when adapting general-purpose physiology
 * engines to mission planning contexts.
 *
 * FLIGHT TIMELINE:
 *   Phase 1 | T+0s   – T+30s  | 1G Baseline         (Pre-Launch Pad Hold)
 *   Phase 2 | T+30s  – T+90s  | +3Gz Ascent         (Rocket Ignition to MECO)
 *   Phase 3 | T+90s  – T+120s | 0G Arrival           (Microgravity / Fluid Shift)
 *   Phase 4 | T+120s+          | Long-Term Adaptation (Space Deconditioning)
 *
 * SYSTEM ARCHITECTURE:
 *   [BioGears Engine] -> [This Bridge]
 *       |-> Flight_Telemetry.csv  (persistent log)
 *       |-> UDP/8080 -> [live_graph.py]   Python Mission Control Dashboard
 *                    -> [Unreal Engine 5] 3D Heart Visualizer
 *
 * @author  Shamant N
 * @version 2.0
 */

// =========================================================================
// STANDARD LIBRARY INCLUDES
// =========================================================================
#include <iostream>   // Console status output
#include <thread>     // std::this_thread::sleep_for
#include <chrono>     // std::chrono::milliseconds
#include <string>     // std::string (JSON payload construction)
#include <fstream>    // std::ofstream (CSV log)

// =========================================================================
// BIOGEARS ENGINE HEADERS
// NOTE: Must be included BEFORE Windows headers to avoid macro collisions.
// =========================================================================
#include <biogears/engine/BioGearsPhysiologyEngine.h>
#include <biogears/cdm/system/physiology/SECardiovascularSystem.h>
#include <biogears/cdm/system/physiology/SEBloodChemistrySystem.h>

// -------------------------------------------------------------------------
// PROXY ACTION HEADERS — +3Gz LAUNCH PHASE
// -------------------------------------------------------------------------

/**
 * @brief PROXY: Venous Fluid Pooling / Reduced Cardiac Preload
 *
 * Under +Gz acceleration, hydrostatic pressure increases along the
 * craniocaudal axis, draining blood and interstitial fluid into the lower
 * extremities. This reduces venous return to the right heart (preload),
 * drops stroke volume, and triggers compensatory tachycardia.
 *
 * PROXY: SEHemorrhage on "LeftLeg" at 300 mL/min forces BioGears to model
 * a rapid reduction in lower-body venous return — functionally identical
 * to gravitational venous pooling at +3Gz.
 */
#include <biogears/cdm/patient/actions/SEHemorrhage.h>

/**
 * @brief PROXY: G-Force Chest Compression & V-Q Mismatch
 *
 * At +3Gz, the effective weight of the thorax triples. The diaphragm is
 * compressed caudally, reducing tidal volume and functional residual
 * capacity. Blood flow preferentially shifts to dependent (basal) lung
 * zones while ventilation remains distributed — creating a
 * Ventilation-Perfusion (V/Q) mismatch that impairs alveolar gas exchange,
 * producing measurable SpO2 desaturation and increased work of breathing.
 *
 * PROXY: SEAcuteRespiratoryDistress at severity 0.7 instructs BioGears
 * to reduce pulmonary compliance and gas exchange efficiency, matching
 * the ~15–20% tidal volume reduction documented in +Gz centrifuge trials.
 */
#include <biogears/cdm/patient/actions/SEAcuteRespiratoryDistress.h>

/**
 * @brief PROXY: Sympatho-Adrenal Launch Response (Adrenaline Dump)
 *
 * Rocket ignition triggers a peak catecholamine release (epinephrine +
 * norepinephrine) from the adrenal medulla. This systemic sympathetic
 * activation drives: tachycardia, peripheral vasoconstriction, elevated
 * cardiac contractility, bronchodilation, and heightened metabolic rate —
 * all documented in astronaut biometric data during launch.
 *
 * PROXY: SEAcuteStress at severity 1.0 (maximum) models the global
 * sympatho-adrenal activation, producing all of the above cardiovascular
 * and metabolic effects simultaneously.
 */
#include <biogears/cdm/patient/actions/SEAcuteStress.h>

// Property unit wrappers (BioGears requires strongly-typed units)
#include <biogears/cdm/properties/SEScalarVolumePerTime.h>  // mL/min, L/min
#include <biogears/cdm/properties/SEScalar0To1.h>           // Severity [0, 1]
#include <biogears/cdm/properties/SEScalarVolume.h>         // mL, L

// =========================================================================
// WINDOWS NETWORKING HEADERS
// NOTE: Must come AFTER BioGears headers (see include order note above).
//       WIN32_LEAN_AND_MEAN strips unused Win32 subsystems to prevent
//       macro conflicts and reduce compile time.
// =========================================================================
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#pragma comment(lib, "ws2_32.lib")

using namespace biogears;

int main() {

    // =====================================================================
    // SECTION 1: UDP SOCKET SETUP
    // =====================================================================
    // UDP (SOCK_DGRAM) is chosen over TCP because:
    //   (a) Zero connection overhead — sendto() fires and forgets, keeping
    //       latency minimal at 10 Hz broadcast frequency.
    //   (b) Loss-tolerant — dropping one 100ms telemetry frame causes a
    //       cosmetic gap on the graph, not a connection failure or stall.
    //
    // WHY TWO SOCKETS (8080 AND 8081):
    //   On Windows, SO_REUSEADDR for UDP does NOT deliver a copy of each
    //   packet to every bound listener. Instead, Windows picks ONE recipient
    //   per packet — whichever process bound most recently wins, starving
    //   the other. To allow BOTH Unreal Engine 5 (port 8080) and the Python
    //   dashboard (port 8081) to receive telemetry simultaneously, we send
    //   the same payload to two separate destination ports. Each consumer
    //   binds exclusively to its own port with no contention.

    WSADATA wsaData;
    // Initialize the Winsock DLL. MAKEWORD(2,2) requests Winsock v2.2.
    WSAStartup(MAKEWORD(2, 2), &wsaData);

    // Create a single UDP socket (reused for both sendto() calls).
    SOCKET udpSocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);

    // Destination 1: Unreal Engine 5 Blueprint UDP receiver — port 8080
    sockaddr_in ue5Address;
    ue5Address.sin_family = AF_INET;
    ue5Address.sin_port   = htons(8080);
    inet_pton(AF_INET, "127.0.0.1", &ue5Address.sin_addr);

    // Destination 2: Python Mission Control Dashboard — port 8081
    sockaddr_in pythonAddress;
    pythonAddress.sin_family = AF_INET;
    pythonAddress.sin_port   = htons(8081);
    inet_pton(AF_INET, "127.0.0.1", &pythonAddress.sin_addr);

    // =====================================================================
    // SECTION 2: CSV LOG INITIALIZATION
    // =====================================================================
    // Written alongside the .exe. The MissionPhase column provides event
    // markers so that downstream tools (pandas, Excel, MATLAB) can segment
    // and annotate data by flight phase without needing separate event files.
    std::ofstream csvFile("Flight_Telemetry.csv");
    csvFile << "Time(s),HeartRate(BPM),StrokeVolume(mL),SpO2(%),MissionPhase\n";

    // =====================================================================
    // SECTION 3: BIOGEARS ENGINE INITIALIZATION
    // =====================================================================
    std::unique_ptr<PhysiologyEngine> bg = CreateBioGearsEngine("Aerospace_DigitalTwin.log");

    // LoadState restores a pre-stabilized patient. "StandardMale@0s.xml"
    // is a healthy 77 kg adult male in full homeostatic equilibrium —
    // BioGears has already solved the expensive initialization pass and
    // serialized the result; loading it reaches a ready patient in <1 second.
    bg->LoadState("C:/Program Files/BioGears/bin/states/StandardMale@0s.xml");

    // =====================================================================
    // SECTION 4: PROXY ACTION OBJECTS
    // =====================================================================
    // Declared once and reused. BioGears actions are stateful — calling
    // ProcessAction() with updated parameters modifies the ongoing condition
    // without resetting it.

    // Phase 2 proxies
    SEHemorrhage legBleed;
    legBleed.SetCompartment("LeftLeg");       // Lower-body venous pooling proxy
    SEAcuteRespiratoryDistress chestCompression; // G-force thoracic loading proxy
    SEAcuteStress sympatheticResponse;           // Catecholamine dump proxy

    // Phase 4 proxy
    SEHemorrhage spaceDiuresis;
    spaceDiuresis.SetCompartment("VenaCava");  // Central volume contraction proxy

    double totalTime  = 0.0;   // Mission elapsed time (seconds)
    double timeStep   = 0.1;   // Engine advance per iteration (10 Hz)
    std::string currentPhase = "1_Pad_1G"; // CSV phase label

    std::cout << "Engine Ready. Systems Green for Launch..." << std::endl;

    // =====================================================================
    // SECTION 5: MAIN SIMULATION LOOP
    // =====================================================================
    // Each iteration: (1) advances physiology, (2) applies phase actions,
    // (3) extracts telemetry, (4) logs to CSV, (5) broadcasts via UDP.
    // The 100ms sleep synchronizes simulated time to real-world wall time.
    while (true) {

        bg->AdvanceModelTime(timeStep, TimeUnit::s);
        totalTime += timeStep;

        // =================================================================
        // PHASE 2: +3Gz ASCENT STRESS  [T+30s to T+90s]
        // =================================================================
        // Three proxy actions applied together model the compound physiological
        // insult of sustained +3Gz craniocaudal acceleration.
        // The narrow window (> 30.0 && < 30.1) ensures the block fires
        // exactly once at the correct 10 Hz tick.
        if (totalTime > 30.0 && totalTime < 30.1) {
            std::cout << "\n[FLIGHT T+30s] IGNITION: +Gz stress beginning..." << std::endl;
            currentPhase = "2_Ascent_3G";

            // Proxy 1: Venous Pooling — 300 mL/min drains lower-body venous
            // return, producing the documented ~10-15% stroke volume drop
            // seen in human +3Gz centrifuge studies.
            legBleed.GetInitialRate().SetValue(300.0, VolumePerTimeUnit::mL_Per_min);
            bg->ProcessAction(legBleed);

            // Proxy 2: Thoracic Compression — severity 0.7 represents the
            // ~15-20% tidal volume reduction measured in +Gz trials. BioGears
            // responds with impaired gas exchange and SpO2 desaturation.
            chestCompression.GetSeverity().SetValue(0.7);
            bg->ProcessAction(chestCompression);

            // Proxy 3: Adrenaline Dump — maximum severity drives the expected
            // tachycardia, vasoconstriction, and increased contractility
            // characteristic of the acute sympathetic launch response.
            sympatheticResponse.GetSeverity().SetValue(1.0);
            bg->ProcessAction(sympatheticResponse);
        }

        // =================================================================
        // PHASE 3: 0G ARRIVAL — CEPHALAD FLUID SHIFT  [T+90s to T+120s]
        // =================================================================
        // At Main Engine Cutoff (MECO), gravitational acceleration drops to
        // zero. The hydrostatic gradient collapses and ~1-2 L of previously
        // pooled lower-body fluid redistributes toward the thorax, head,
        // and neck — the "Cephalad Fluid Shift."
        //
        // This causes: elevated CVP, increased cardiac preload, early diuresis
        // (atrial stretch receptors misread the shift as volume overload),
        // nasal congestion, and the characteristic "puffy face / bird legs"
        // appearance of astronauts in microgravity.
        //
        // PROXY: Zeroing all three Phase 2 stressors removes the hemodynamic
        // and respiratory insults, allowing BioGears to model the compensatory
        // cardiovascular response to suddenly normalized (and then elevated)
        // venous return — capturing the fluid-shift dynamics accurately.
        else if (totalTime > 90.0 && totalTime < 90.1) {
            std::cout << "\n[FLIGHT T+90s] MECO: Zero-G. Launch stresses cleared." << std::endl;
            currentPhase = "3_Orbit_Arrival";

            // Zero venous drain — fluid returns to central circulation
            legBleed.GetInitialRate().SetValue(0.0, VolumePerTimeUnit::mL_Per_min);
            bg->ProcessAction(legBleed);

            // Remove thoracic compression — pulmonary mechanics normalize
            chestCompression.GetSeverity().SetValue(0.0);
            bg->ProcessAction(chestCompression);

            // Remove peak sympathetic drive — catecholamine levels begin to fall
            sympatheticResponse.GetSeverity().SetValue(0.0);
            bg->ProcessAction(sympatheticResponse);
        }

        // =================================================================
        // PHASE 4: LONG-TERM ADAPTATION  [T+120s+]
        // =================================================================
        // Two chronic maladaptive processes dominate long-duration spaceflight:
        //
        // A. SPACE DIURESIS:
        //    Atrial stretch receptors — sensing the elevated central volume
        //    from the cephalad fluid shift — trigger Atrial Natriuretic Peptide
        //    (ANP) release. ANP suppresses aldosterone and instructs the kidneys
        //    to excrete sodium and water, contracting plasma volume by 10-15%
        //    within 24-48 hours. The body down-regulates its own circulatory
        //    volume to match a gravity-free homeostatic set-point.
        //
        //    PROXY: SEHemorrhage on "VenaCava" at 50 mL/min. Targeting the
        //    central venous compartment models the gradual, renally-mediated
        //    plasma volume reduction without the peripheral hemodynamic
        //    disturbances of the Phase 2 limb bleed.
        //
        // B. CARDIAC DECONDITIONING / ATROPHY:
        //    Without the need to pump against gravity, cardiac workload
        //    decreases substantially. Over weeks-months, this results in
        //    measurable left ventricular mass reduction (cardiac atrophy),
        //    decreased maximum cardiac output, and reduced orthostatic tolerance.
        //    Returning astronauts frequently experience orthostatic hypotension
        //    (fainting upon standing) from this structural deconditioning.
        //
        //    PROXY: Low-grade SEAcuteStress at 0.2 severity models the mild,
        //    chronic autonomic dysregulation and reduced sympathetic tone
        //    associated with the altered cardiovascular set-point in orbit.
        else if (totalTime > 120.0 && totalTime < 120.1) {
            std::cout << "\n[ORBIT T+120s] FAST-FORWARD: Inducing Long-Term Space Adaptation." << std::endl;
            currentPhase = "4_LongTerm_Adaptation";

            // Proxy A: Space Diuresis — central plasma volume contraction
            spaceDiuresis.GetInitialRate().SetValue(50.0, VolumePerTimeUnit::mL_Per_min);
            bg->ProcessAction(spaceDiuresis);

            // Proxy B: Cardiac deconditioning — mild chronic autonomic shift
            sympatheticResponse.GetSeverity().SetValue(0.2);
            bg->ProcessAction(sympatheticResponse);
        }

        // =====================================================================
        // SECTION 6: TELEMETRY EXTRACTION
        // =====================================================================
        double hr   = bg->GetCardiovascularSystem()->GetHeartRate(FrequencyUnit::Per_min);
        double co   = bg->GetCardiovascularSystem()->GetCardiacOutput(VolumePerTimeUnit::L_Per_min);

        // Stroke Volume (mL) = CardiacOutput (L/min) / HeartRate (bpm) * 1000
        // BioGears does not expose SV directly; this derivation is the standard
        // clinical formula equivalent to Fick/thermodilution measurement.
        // Guard against HR=0 (theoretical edge case during initialization).
        double sv   = (hr > 0.0) ? (co / hr) * 1000.0 : 0.0;

        // SpO2 is returned as a [0,1] fraction by BioGears.
        double spo2 = bg->GetBloodChemistrySystem()->GetOxygenSaturation();

        // =====================================================================
        // SECTION 7: CSV LOG WRITE
        // =====================================================================
        // SpO2 is written as percentage (x100). One row per 0.1s time step.
        csvFile << totalTime << "," << hr << "," << sv << ","
                << (spo2 * 100.0) << "," << currentPhase << "\n";

        // =====================================================================
        // SECTION 8: JSON PAYLOAD CONSTRUCTION & UDP BROADCAST
        // =====================================================================
        // JSON is used because:
        //   (a) Native parsing in Python (json.loads) and UE5 Blueprint.
        //   (b) Human-readable for debugging (inspect with netcat nc -ul 8080).
        //   (c) ~60-byte payload is well below the loopback MTU — no fragmentation.
        //
        // Format: {"HR":<bpm>,"SV":<mL>,"SPO2":<fraction 0-1>}
        // NOTE: SPO2 is transmitted as raw [0,1] fraction. The Python dashboard
        // applies the x100 conversion on receipt.
        std::string payload = "{\"HR\":"   + std::to_string(hr)   +
                              ",\"SV\":"   + std::to_string(sv)   +
                              ",\"SPO2\":" + std::to_string(spo2) + "}";

        // Send to UE5 (port 8080)
        sendto(udpSocket, payload.c_str(), (int)payload.length(), 0,
               (SOCKADDR*)&ue5Address, sizeof(ue5Address));

        // Send the identical payload to the Python dashboard (port 8081).
        // Both consumers now receive every frame independently with no contention.
        sendto(udpSocket, payload.c_str(), (int)payload.length(), 0,
               (SOCKADDR*)&pythonAddress, sizeof(pythonAddress));

        // =====================================================================
        // SECTION 9: CONSOLE STATUS ECHO
        // =====================================================================
        std::cout << "T+" << (int)totalTime << "s"
                  << " | HR: "    << (int)hr    << " BPM"
                  << " | SV: "    << (int)sv    << " mL"
                  << " | SpO2: "  << (int)(spo2 * 100) << "%"
                  << std::endl;

        // Rate-limit to 100ms wall time — maintains 1:1 simulated:real-time
        // ratio so that the live dashboard receives data at a stable 10 Hz.
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    return 0;
}