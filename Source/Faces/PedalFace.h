#pragma once
#include "../UI/FaceLayout.h"

// Optional artwork for a pedal. A pedal without a face gets the plain generic strip.
// Faces live outside the DSP classes so pedals stay reusable in other plugins.
class PedalFace
{
public:
    virtual ~PedalFace() = default;
    virtual void paint(juce::Graphics&, const FaceLayout&, bool active) = 0;
    virtual juce::Colour labelColour() const { return juce::Colours::black; }

    // Rendered-image support (all optional). Defaults = plain vector controls.
    virtual bool drawsLabels() const { return false; }                       // labels baked into the artwork?
    virtual juce::LookAndFeel* knobLookAndFeel() { return nullptr; }         // nullptr = vector knob
    virtual juce::Rectangle<float> knobBounds(juce::Rectangle<float> r) const { return r; }   // area the knob draws in
    virtual juce::Rectangle<float> switchBounds(juce::Rectangle<float> r) const { return r; }
    virtual const juce::Image* footswitchImage(bool /*down*/) const { return nullptr; }
    virtual juce::Rectangle<float> toggleBounds(juce::Rectangle<float> r) const { return r; }
    virtual const juce::Image* toggleImage(bool /*up*/) const { return nullptr; }
};

// Returns the face for a pedal id, or nullptr. Register new faces in PedalFaces.cpp.
std::unique_ptr<PedalFace> createFaceFor(const juce::String& pedalId);
