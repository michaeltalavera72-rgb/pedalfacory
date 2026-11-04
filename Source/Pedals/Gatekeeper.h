#pragma once
#include "PedalBase.h"
#include <vector>
#include <cmath>

// Gatekeeper: a noise gate in the spirit of the Boss NF-1 Noise Gate (service sheet ET-45C), shown under
// our own name and artwork. Circuit read: see claude/nf1-gate-trace.md. The NF-1 is a soft downward expander:
//
//   SIGNAL: Q1 emitter follower -> 22k series -> JFET Q3 (2SK30A) shunting to ground as a voltage-controlled
//           resistor -> Q2 emitter follower. Attenuation = Rjfet / (22k + Rjfet): smooth, never a hard chop,
//           ~20-25 dB of reduction at the factory trim (VR3 "sustain level").
//   SIDE CHAIN: SENS pot -> uPC741 x1000 (60 dB) -> Q4 phase splitter -> Q5/Q6 full-wave rectifier
//           -> envelope cap: attack ~0.5 ms (470R charge), release up to ~2 s (DECAY 2MB discharge).
//
// What we keep: SENS + DECAY, the fast attack, the long natural fade (a smooth glide in dB, never a chop).
// What we add for a board full of high-gain pedals:
//   * HARD / SOFT mini toggle (how far the gate closes): SOFT = -25 dB like the NF-1's factory trim,
//     HARD = full mute. Michael's artwork has two knobs, so the old RANGE knob became this toggle (v29b).
//     Knobs are printed THRESHOLD (= the NF-1's SENS) and RELEASE (= DECAY); ids stay ng_sens / ng_decay.
//   * Hysteresis (closes 6 dB below where it opens) + 40 ms hold, so held notes don't chatter.
//   * KEYED "loop" topology (Boss NS-2 / ISP Decimator style): the detector listens to the clean guitar at
//     the gate's slot (put it first), but the gain reduction is applied after the drive pedals, via the
//     board's return stage (hasReturnStage / processReturn). The hiss those pedals amplify by 40-60 dB is
//     cut where it actually exists, while the gate still tracks the uncompressed, easy-to-read clean signal.
class Gatekeeper : public PedalBase
{
public:
    juce::String getId() const override { return "ng"; }
    juce::String getName() const override { return "Gatekeeper"; }
    juce::String getBasedOn() const override
    {
        return "Boss NF-1 Noise Gate (1979, JFET expander), keyed from the clean guitar like a noise-suppressor loop";
    }

    void addParameters(juce::AudioProcessorValueTreeState::ParameterLayout& l) override
    {
        using P = juce::AudioParameterFloat;
        auto attrs = [](std::function<juce::String(float, int)> f)
        { return juce::AudioParameterFloatAttributes().withStringFromValueFunction(std::move(f)); };
        l.add(std::make_unique<juce::AudioParameterBool>(juce::ParameterID{"ng_bypass",1}, "Gatekeeper Bypass", false));
        l.add(std::make_unique<P>(juce::ParameterID{"ng_sens",1}, "Threshold",
            juce::NormalisableRange<float>(0.0f, 1.0f), 0.5f,
            attrs([](float v, int) { return juce::String(juce::roundToInt(thresholdDb(v))) + " dB"; })));
        l.add(std::make_unique<P>(juce::ParameterID{"ng_decay",1}, "Release",
            juce::NormalisableRange<float>(0.0f, 1.0f), 0.4f,
            attrs([](float v, int) { const float t = decaySeconds(v);
                return t < 1.0f ? juce::String(juce::roundToInt(t * 1000.0f)) + " ms" : juce::String(t, 2) + " s"; })));
        l.add(std::make_unique<juce::AudioParameterBool>(juce::ParameterID{"ng_hard",1}, "Gatekeeper Hard", true));
        knobIds = { "ng_sens", "ng_decay" };   // THRESHOLD, RELEASE (left to right on the face)
        toggleId = "ng_hard"; toggleLabel = "HARD";   // up = HARD (mute), down = SOFT (-25 dB)
    }
    void bindParameters(juce::AudioProcessorValueTreeState& s) override
    {
        bypassParam = s.getRawParameterValue("ng_bypass");
        sens  = s.getRawParameterValue("ng_sens");
        decay = s.getRawParameterValue("ng_decay");
        hard  = s.getRawParameterValue("ng_hard");
    }

    void prepare(const juce::dsp::ProcessSpec& spec) override
    {
        sr = spec.sampleRate;
        // Room for any block the host is likely to send; longer blocks reuse the last gain (see processReturn).
        gains.assign((size_t) juce::jmax<int>((int) spec.maximumBlockSize, 8192), 1.0f);
        // Detector band: ignore rumble/DC below 100 Hz and most of the hiss above 5 kHz.
        hp = juce::dsp::IIR::Coefficients<float>::makeHighPass(sr, 100.0);
        lp = juce::dsp::IIR::Coefficients<float>::makeLowPass(sr, 5000.0);
        hpF.coefficients = hp; lpF.coefficients = lp;
        envAtk = coeff(0.0002); envRel = coeff(0.020);      // level follower: 0.2 ms up, 20 ms down
        gainAtk = coeff(0.0005);                            // opening: NF-1's ~0.5 ms envelope charge
        holdSamples = (int) (0.040 * sr);
        reset();
    }
    void reset() override
    {
        hpF.reset(); lpF.reset();
        env = 0.0f; gainDb = 0.0f; open = false; hold = 0; filled = 0;
        std::fill(gains.begin(), gains.end(), 1.0f);
    }

    // Slot stage: listen only. The signal passes through untouched; the gain curve is stored for the return.
    void process(juce::AudioBuffer<float>& buf) override
    {
        const float thrOpen  = thresholdDb(sens->load());
        const float thrClose = thrOpen - hysteresisDb;
        const float floorDb  = hard->load() >= 0.5f ? muteDb : softDb;
        const float relCoef  = coeff(decaySeconds(decay->load()) / 4.6);   // ~99% of the way in DECAY seconds

        const int n = buf.getNumSamples();
        const float* x = buf.getReadPointer(0);
        filled = juce::jmin(n, (int) gains.size());
        for (int i = 0; i < n; ++i)
        {
            // full-wave rectified, band-limited detector (the 741 / Q4-Q6 side chain)
            const float d = std::abs(lpF.processSample(hpF.processSample(x[i])));
            env += (d > env ? envAtk : envRel) * (d - env);
            const float envDb = 20.0f * std::log10(env + 1.0e-9f);

            if (envDb >= thrOpen)            { open = true; hold = holdSamples; }
            else if (envDb < thrClose)       { if (hold > 0) --hold; else open = false; }

            // closed -> HARD (mute) or SOFT (-25 dB). (A sloped expander knee made the gain wobble with the hiss itself; the NF-1's
            // softness comes from its long, smooth release, which the dB-domain DECAY glide below keeps.)
            const float target = open ? 0.0f : floorDb;
            gainDb += (target > gainDb ? gainAtk : relCoef) * (target - gainDb);

            if (i < filled) gains[(size_t) i] = gainDb <= muteDb + 0.5f ? 0.0f : juce::Decibels::decibelsToGain(gainDb);
        }
        currentGainDb.store(gainDb);
    }

    // Return stage: the board calls this after the drive pedals (before any time-based pedal).
    bool hasReturnStage() const override { return true; }
    void processReturn(juce::AudioBuffer<float>& buf) override
    {
        const int n = buf.getNumSamples();
        float* y = buf.getWritePointer(0);
        const float last = filled > 0 ? gains[(size_t) filled - 1] : 1.0f;
        for (int i = 0; i < n; ++i) y[i] *= i < filled ? gains[(size_t) i] : last;
    }

    // Gate state for the UI (e.g. an "open" LED): current gain in dB, 0 = fully open.
    std::atomic<float> currentGainDb { 0.0f };

    // Knob laws (also used for the value text)
    static float thresholdDb(float s)  { return -30.0f - 55.0f * s; }                      // -30 .. -85 dBFS
    static float decaySeconds(float d) { return 0.02f * std::pow(100.0f, d); }             // 20 ms .. 2 s (NF-1 max)

private:
    static constexpr float muteDb = -120.0f, softDb = -25.0f, hysteresisDb = 6.0f;
    float coeff(double seconds) const { return (float) (1.0 - std::exp(-1.0 / (juce::jmax(1.0e-5, seconds) * sr))); }

    double sr = 48000.0;
    std::atomic<float> *sens = nullptr, *decay = nullptr, *hard = nullptr;
    juce::dsp::IIR::Coefficients<float>::Ptr hp, lp;
    juce::dsp::IIR::Filter<float> hpF, lpF;
    float envAtk = 0, envRel = 0, gainAtk = 0;
    float env = 0.0f, gainDb = 0.0f;
    bool open = false;
    int hold = 0, holdSamples = 0, filled = 0;
    std::vector<float> gains;
};
