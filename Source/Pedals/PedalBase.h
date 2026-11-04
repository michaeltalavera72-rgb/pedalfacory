#pragma once
#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_dsp/juce_dsp.h>
#include <array>

// Every pedal implements this interface. The board owns pedals in a vector
// and runs them in order (guitar -> pedal 1 -> pedal 2 -> ... -> output).
class PedalBase
{
public:
    virtual ~PedalBase() = default;
    virtual juce::String getId() const = 0;          // stable id, used in parameter ids
    virtual juce::String getName() const = 0;        // display name
    // Which real pedal/circuit this models, shown as a tooltip on the pedal's name.
    // Real product names only identify the circuit; the pedal is shown under its own name and artwork.
    virtual juce::String getBasedOn() const { return {}; }
    virtual void addParameters(juce::AudioProcessorValueTreeState::ParameterLayout&) = 0;
    virtual void bindParameters(juce::AudioProcessorValueTreeState&) = 0;
    virtual void prepare(const juce::dsp::ProcessSpec&) = 0;
    virtual void process(juce::AudioBuffer<float>&) = 0;
    virtual void reset() {}

    // Main footswitch ("<id>_bypass"). The board only calls process() while isActive() is true.
    virtual bool isActive() const { return primaryOn() || secondaryOn(); }
    bool primaryOn() const { return bypassParam == nullptr || bypassParam->load() < 0.5f; }
    std::atomic<float>* bypassParam = nullptr;

    // Optional second footswitch (e.g. a boost). Empty id = the pedal has only one footswitch.
    // The parameter is a bool where true = ON. Pedals with one must check both states in process().
    virtual juce::String secondarySwitchId() const { return {}; }
    virtual juce::String secondarySwitchLabel() const { return {}; }
    bool secondaryOn() const { return secondaryParam != nullptr && secondaryParam->load() >= 0.5f; }
    std::atomic<float>* secondaryParam = nullptr;

    juce::StringArray knobIds;   // parameter ids the editor should show as knobs
    juce::StringArray detentKnobIds;   // knobs with a centre detent: snap to noon, double-click = noon
    // Optional mini toggle switch on the face (e.g. a voicing switch). Bool parameter, true = up/ON.
    // Not a footswitch: it never bypasses the pedal.
    juce::String toggleId, toggleLabel;

    // Optional "effects loop" return stage (e.g. a keyed noise gate). When hasReturnStage() is true the board
    // calls process() at the pedal's slot, then processReturn() on the same block after the later pedals:
    // just before the first time-based pedal, or at the end of the chain.
    virtual bool hasReturnStage() const { return false; }
    virtual void processReturn(juce::AudioBuffer<float>&) {}
    // Delay/reverb-type pedals return true so a keyed gate's return lands before them (tails ring out).
    virtual bool isTimeBased() const { return false; }
};
