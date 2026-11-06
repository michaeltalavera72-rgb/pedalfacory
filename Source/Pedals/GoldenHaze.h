#pragma once
#include "PedalBase.h"

// Golden Haze: a model of the Earthquake Devices Acapulco Gold "power amp distortion" (shown under our own name
// and artwork). Built from schematics/Earthquake Devices/EQD - Acapulco Gold.pdf (a third-party drawing).
// Two LM386 power-amp chips in a row, one knob. Signal path, in volts, oversampled 4x:
//
//   IN -> C1 10u into R1 1M || the LM386's internal 50k input resistor (DC coupling only).
//   OP1 LM386, C2 10u across pins 1-8: the internal network gives gain 20 at DC rising to 200 above ~118 Hz
//       (zero 11.8 Hz from 1.35k x 10u, pole 10x higher): Av = 20 + 180 * HP(118 Hz). So the lowest notes are
//       driven a little less than the rest - the bass stays firm instead of farting out.
//       Supply = 9 V through VD1 1N4001 (~8.35 V), output idles at Vs/2. Unloaded swing to ~0.9 V below the
//       top rail and ~0.45 V above ground -> asymmetric clipping (even harmonics). The LM386's low loop gain
//       at x200 makes the knee softer than an op-amp's.
//   C3 1u -> R2 68k -> + input of OP2, with C4 4n7 to ground and OP2's internal 50k to ground:
//       divider 50/118 (-7.5 dB) and a first-order low-pass at 1/(2 pi (68k || 50k) 4n7) = ~1.18 kHz.
//       That RC is the pedal's only tone shaping: it takes the fizz off the first stage's square wave.
//   OP2 LM386, pins 1-8 open: flat gain 20 - the low-passed signal is clipped again at the same rails.
//   C5 1u -> R3 A100k VOLUME (wiper = OUT).
// About 72 dB of gain in total, so the pedal is always fully saturated; VOLUME is the only control and the
// guitar's volume knob is the gain control (as on the real one).
class GoldenHaze : public PedalBase
{
public:
    juce::String getId() const override { return "gh"; }
    juce::String getName() const override { return "Golden Haze"; }
    PedalCategory getCategory() const override { return PedalCategory::Distortion; }
    juce::String getBasedOn() const override { return "Earthquake Devices Acapulco Gold (power amp distortion, two LM386 chips)"; }

    // Tooltip text for each control (the editor adds the control's name on top).
    juce::String describe(const juce::String& id) const override
    {
        if (id == "gh_bypass") return "Footswitch: turns Golden Haze on or off.";
        if (id == "gh_volume") return "Output level - the only knob. The distortion is always fully cranked, like a power amp "
                                      "turned all the way up. Roll back your guitar's volume knob to clean it up.";
        return {};
    }

    void addParameters(juce::AudioProcessorValueTreeState::ParameterLayout& l) override
    {
        l.add(std::make_unique<juce::AudioParameterBool>(juce::ParameterID{"gh_bypass",1}, "Golden Haze Bypass", false));
        l.add(std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"gh_volume",1}, "Volume", 0.0f, 1.0f, 0.5f));
        knobIds = { "gh_volume" };
    }
    void bindParameters(juce::AudioProcessorValueTreeState& s) override
    {
        bypassParam = s.getRawParameterValue("gh_bypass");
        volume = s.getRawParameterValue("gh_volume");
    }
    void prepare(const juce::dsp::ProcessSpec& spec) override
    {
        sr = spec.sampleRate;
        oversampler = std::make_unique<juce::dsp::Oversampling<float>>(
            spec.numChannels, 2, juce::dsp::Oversampling<float>::filterHalfBandPolyphaseIIR);   // 4x
        oversampler->initProcessing(spec.maximumBlockSize);
        const double fs = sr * 4.0;
        gIn   = coeff(3.0, fs);       // input coupling (C1 into ~48k is 0.33 Hz; 3 Hz keeps DC out)
        gG1   = coeff(117.9, fs);     // OP1 gain network: 20 -> 200 (1.35k x 10u zero, pole at 10x)
        gBw1  = coeff(40000.0, fs);   // OP1 closed-loop bandwidth at x200
        gC3   = coeff(1.35, fs);      // C3 1u into 68k + 50k
        gRc   = coeff(1175.0, fs);    // R2 68k || 50k with C4 4n7
        gC5   = coeff(1.6, fs);       // C5 1u into the 100k volume pot
        gDc   = coeff(5.0, sr);       // output DC guard
        outGain.reset(sr, 0.05);
        outGain.setCurrentAndTargetValue(targetGain());
        reset();
    }
    void reset() override
    {
        for (auto& c : ch) c = {};
        if (oversampler) oversampler->reset();
    }

    void process(juce::AudioBuffer<float>& buf) override
    {
        outGain.setTargetValue(targetGain());

        juce::dsp::AudioBlock<float> block(buf);
        auto up = oversampler->processSamplesUp(block);
        for (size_t c = 0; c < up.getNumChannels() && c < ch.size(); ++c)
        {
            auto& s = ch[c];
            auto* x = up.getChannelPointer(c);
            for (size_t i = 0; i < up.getNumSamples(); ++i)
            {
                double v = (double) x[i] * 0.5;                          // full scale ~ 0.5 V guitar
                v -= lowpass(s.in, v, gIn);

                // OP1: x20 at DC, x200 above ~118 Hz, then the output stage swing limits
                const double hp = v - lowpass(s.g1, v, gG1);
                double u = 20.0 * v + 180.0 * hp;
                u = lowpass(s.bw1, u, gBw1);
                u = lm386(u);

                // C3 / R2 68k / C4 4n7 / OP2's 50k input resistor
                u -= lowpass(s.c3, u, gC3);
                u = (50.0 / 118.0) * lowpass(s.rc, u, gRc);

                // OP2: flat x20, clipped again; C5 into the volume pot
                double w = lm386(20.0 * u);
                w -= lowpass(s.c5, w, gC5);
                x[i] = (float) w;
            }
        }
        oversampler->processSamplesDown(block);

        const int n = buf.getNumSamples();
        for (int i = 0; i < n; ++i)
        {
            const float g = outGain.getNextValue();
            for (int c = 0; c < buf.getNumChannels() && c < (int) ch.size(); ++c)
            {
                auto* x = buf.getWritePointer(c);
                float o = x[i] * g;
                o -= (float) lowpass(ch[(size_t) c].dc, o, gDc);
                x[i] = o;
            }
        }
    }

    // LM386 output swing on ~8.35 V, around Vs/2 (exposed for tests): soft knee, asymmetric limits.
    static double lm386(double v)
    {
        const double lim = v >= 0.0 ? posSwing : negSwing;
        const double t = std::abs(v) / lim;
        const double y = lim * t / std::cbrt(1.0 + t * t * t);       // k = 3 knee
        return v >= 0.0 ? y : -y;
    }

private:
    struct Ch { double in = 0, g1 = 0, bw1 = 0, c3 = 0, rc = 0, c5 = 0, dc = 0; };
    std::array<Ch, 2> ch;
    double sr = 48000.0;
    double gIn = 0, gG1 = 0, gBw1 = 0, gC3 = 0, gRc = 0, gC5 = 0, gDc = 0;
    juce::SmoothedValue<float> outGain;
    std::atomic<float>* volume{};
    std::unique_ptr<juce::dsp::Oversampling<float>> oversampler;

    static constexpr double posSwing = 4.17 - 0.90, negSwing = 4.17 - 0.45;   // volts from the idle point
    static constexpr float levelScale = 0.45f;    // volts -> digital; calibrated: same loudness as the Valve Howler at noon (-18 dBFS sine in)

    float targetGain() const { return volume != nullptr ? levelScale * (float) audioTaper(volume->load()) : 0.0f; }
    static double audioTaper(double x) { return (std::pow(10.0, 2.0 * x) - 1.0) / 99.0; }      // A100k, ~9 % at noon
    static double coeff(double fc, double fs) { const double g = std::tan(juce::MathConstants<double>::pi * fc / fs); return g / (1.0 + g); }
    static double lowpass(double& s, double in, double g) { const double v = (in - s) * g; const double y = v + s; s = y + v; return y; }
};
