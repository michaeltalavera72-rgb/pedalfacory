#pragma once
#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_audio_processors/juce_audio_processors.h>
#include "StompboxControls.h"

// Global section, below the pedal row: the Semitone Transposer as a slim rack panel.
//   [footswitch + LED]  [TRANSPOSE big stepped knob]  [display: -2 st / Low E -> D . D Standard]  [MIX] [LEVEL]  [LIVE/STUDIO]
// Vector drawing for now (a Blender render can replace it later, like the pedals).
class TransposerPanel : public juce::Component, private juce::Timer
{
public:
    static constexpr int panelH = 118;

    explicit TransposerPanel(juce::AudioProcessorValueTreeState& s, std::function<int()> studioLatencyFn)
        : state(s), studioLatency(std::move(studioLatencyFn))
    {
        using namespace juce;
        const float start = MathConstants<float>::pi * 1.25f, end = MathConstants<float>::pi * 2.75f;   // -135..+135 deg
        for (auto* k : { &transpose, &mix, &level })
        {
            k->setSliderStyle(Slider::RotaryVerticalDrag);
            k->setTextBoxStyle(Slider::NoTextBox, false, 0, 0);
            k->setRotaryParameters(start, end, true);
            k->setLookAndFeel(&knobLook);
            addAndMakeVisible(*k);
        }
        transpose.setMouseDragSensitivity(300);                        // ~12 px per semitone
        transpose.setDoubleClickReturnValue(true, 0.0);               // double-click = 0 st
        mix.setDoubleClickReturnValue(true, 100.0);
        level.setDoubleClickReturnValue(true, 0.0);
        transpose.setTooltip("Transpose in whole semitones (-12..+12). Double-click: 0 st");
        mix.setTooltip("Mix: 100 % = transposed only, 0 % = original only");
        level.setTooltip("Level of the transposer output (-24..+12 dB). Double-click: 0 dB");
        onSwitch.setTooltip("Transposer on/off");
        mode.setTooltip("LIVE: low delay for playing (attacks ~3 ms).\n"
                        "STUDIO: smoother on big chords and octaves, but ~85 ms delay (reported to your DAW).");
        addAndMakeVisible(onSwitch); addAndMakeVisible(mode);

        tAtt = std::make_unique<AudioProcessorValueTreeState::SliderAttachment>(state, "gx_transpose", transpose);
        mAtt = std::make_unique<AudioProcessorValueTreeState::SliderAttachment>(state, "gx_mix", mix);
        lAtt = std::make_unique<AudioProcessorValueTreeState::SliderAttachment>(state, "gx_level", level);
        onAtt = std::make_unique<AudioProcessorValueTreeState::ButtonAttachment>(state, "gx_on", onSwitch);
        modeAtt = std::make_unique<AudioProcessorValueTreeState::ButtonAttachment>(state, "gx_studio", mode);
        startTimerHz(15);
    }
    ~TransposerPanel() override
    {
        for (auto* k : { &transpose, &mix, &level }) k->setLookAndFeel(nullptr);
    }

    // Note hint for the display, relative to the low E string.
    static juce::String hintFor(int st)
    {
        static const char* flat[]  = { "C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B" };
        static const char* sharp[] = { "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B" };
        if (st == 0) return "E Standard";
        const int idx = ((4 + st) % 12 + 12) % 12;
        const juce::String n = st < 0 ? flat[idx] : sharp[idx];
        const auto arrow = juce::String::fromUTF8(" \xe2\x86\x92 ");          // " -> " as an arrow
        if (st == -12) return "Low E" + arrow + "E  (octave down)";
        if (st == 12)  return "Low E" + arrow + "E  (octave up)";
        return "Low E" + arrow + n + "   " + juce::String::fromUTF8("\xc2\xb7") + "   " + n + " Standard";
    }
    static juce::String valueText(int st) { return (st > 0 ? "+" : "") + juce::String(st) + " st"; }

    void paint(juce::Graphics& g) override
    {
        using namespace juce;
        auto r = getLocalBounds().toFloat().reduced(4.0f, 2.0f);
        // panel: dark anodised plate with a fine brushed texture, bevel, four screws
        g.setColour(Colours::black.withAlpha(0.45f)); g.fillRoundedRectangle(r.translated(0, 3), 7.0f);
        g.setGradientFill(ColourGradient(Colour(0xff2c3035), r.getX(), r.getY(), Colour(0xff17191c), r.getX(), r.getBottom(), false));
        g.fillRoundedRectangle(r, 7.0f);
        g.setColour(Colours::white.withAlpha(0.025f));
        for (float y = r.getY() + 3; y < r.getBottom() - 3; y += 2.0f) g.drawHorizontalLine((int) y, r.getX() + 6, r.getRight() - 6);
        g.setColour(Colours::white.withAlpha(0.10f)); g.drawRoundedRectangle(r.reduced(0.5f), 7.0f, 1.0f);
        for (auto p : { r.getTopLeft() + Point<float>(10, 10), r.getTopRight() + Point<float>(-10, 10),
                        r.getBottomLeft() + Point<float>(10, -10), r.getBottomRight() + Point<float>(-10, -10) })
            drawScrew(g, p);

        const auto amber = Colour(0xffffb347), ink = Colour(0xffd9d4c7);
        // title + LED
        g.setColour(ink);
        g.setFont(FontOptions(12.5f, Font::bold));
        g.drawText("SEMITONE", titleArea.withHeight(16.0f), Justification::centred);
        g.drawText("TRANSPOSER", titleArea.withTrimmedTop(16.0f).withHeight(16.0f), Justification::centred);
        const bool on = state.getRawParameterValue("gx_on")->load() >= 0.5f;
        drawLed(g, ledArea, on);

        // knob scale: 25 ticks for TRANSPOSE, 0 marked
        drawTicks(g, transpose.getBounds().toFloat(), 25, 12, ink);
        drawTicks(g, mix.getBounds().toFloat(), 11, -1, ink.withAlpha(0.6f));
        drawTicks(g, level.getBounds().toFloat(), 13, 8, ink.withAlpha(0.6f));     // 0 dB = tick 8 of 13 (-24..+12, 3 dB steps)
        g.setFont(FontOptions(13.5f, Font::bold));
        g.setColour(ink);
        auto lab = [&](Slider& k, const String& t) { g.drawText(t, k.getBounds().withY(k.getBottom() - 1).withHeight(17).expanded(20, 0), Justification::centred); };
        lab(transpose, "TRANSPOSE"); lab(mix, "MIX"); lab(level, "LEVEL");
        g.setFont(FontOptions(9.5f));
        g.setColour(ink.withAlpha(0.6f));
        {   // -12 / +12 at the ends of the scale
            const auto kb = transpose.getBounds().toFloat();
            const float R = kb.getWidth() * 0.5f + 9.0f, dx = R * 0.7071f;
            const auto c = kb.getCentre();
            g.drawText("-12", Rectangle<float>(c.x - dx - 22.0f, c.y + dx - 4.0f, 22.0f, 12.0f), Justification::centredRight);
            g.drawText("+12", Rectangle<float>(c.x + dx, c.y + dx - 4.0f, 22.0f, 12.0f), Justification::centredLeft);
        }
        // small value readouts under MIX / LEVEL
        g.setColour(amber.withAlpha(0.85f));
        g.setFont(FontOptions(13.5f, Font::bold));
        auto val = [&](Slider& k, const String& t) { g.drawText(t, k.getBounds().withY(k.getBottom() + 15).withHeight(17).expanded(20, 0), Justification::centred); };
        val(mix, String(roundToInt(mix.getValue())) + " %");
        val(level, (level.getValue() > 0.05 ? "+" : "") + String(level.getValue(), 1) + " dB");

        // display: LCD window
        auto d = displayArea;
        g.setColour(Colours::black.withAlpha(0.6f)); g.fillRoundedRectangle(d.translated(0, 1.5f), 5.0f);
        g.setGradientFill(ColourGradient(Colour(0xff0b0f0c), d.getX(), d.getY(), Colour(0xff121a14), d.getX(), d.getBottom(), false));
        g.fillRoundedRectangle(d, 5.0f);
        g.setColour(Colours::white.withAlpha(0.08f)); g.drawRoundedRectangle(d.reduced(0.5f), 5.0f, 1.0f);
        const int st = roundToInt(transpose.getValue());
        const float glow = on ? 1.0f : 0.35f;
        auto inner = d.reduced(10.0f, 6.0f);
        g.setColour(amber.withAlpha(0.55f * glow));
        g.setFont(FontOptions(10.0f, Font::bold));
        g.drawText("TRANSPOSE", inner.removeFromTop(13.0f), Justification::centredLeft);
        g.setColour(amber.withAlpha(glow));
        g.setFont(FontOptions(30.0f, Font::bold));
        g.drawText(valueText(st), inner.removeFromTop(34.0f), Justification::centred);
        g.setColour(amber.withAlpha(0.8f * glow));
        g.setFont(FontOptions(12.0f));
        g.drawText(hintFor(st), inner, Justification::centred);

        // mode labels around the mini toggle
        const bool studio = mode.getToggleState();
        auto m = mode.getBounds().toFloat();
        g.setFont(FontOptions(10.0f, Font::bold));
        g.setColour(ink.withAlpha(studio ? 1.0f : 0.45f));
        g.drawText("STUDIO", m.withY(m.getY() - 13).withHeight(12).expanded(24, 0), Justification::centred);
        g.setColour(ink.withAlpha(studio ? 0.45f : 1.0f));
        g.drawText("LIVE", m.withY(m.getBottom() + 1).withHeight(12).expanded(24, 0), Justification::centred);
        g.setFont(FontOptions(9.5f));
        g.setColour(amber.withAlpha(0.8f));
        const double ms = studioLatency ? studioLatency() * 1000.0 / juce::jmax(1.0, sampleRate()) : 85.0;
        g.drawText(studio ? "~" + String(roundToInt(ms)) + " ms delay" : "attacks ~3 ms",
                   m.withY(m.getBottom() + 14).withHeight(12).expanded(30, 0), Justification::centred);
    }

    void resized() override
    {
        using namespace juce;
        auto r = getLocalBounds().reduced(16, 8);
        const int contentW = 648;
        r = r.withSizeKeepingCentre(jmin(contentW, r.getWidth()), r.getHeight());
        // left: footswitch + LED + title
        auto left = r.removeFromLeft(96);
        titleArea = left.removeFromTop(34).toFloat();
        ledArea = left.removeFromTop(14).toFloat().withSizeKeepingCentre(12, 12);
        onSwitch.setBounds(left.withSizeKeepingCentre(44, 44));
        r.removeFromLeft(10);
        // big TRANSPOSE knob
        auto tk = r.removeFromLeft(88);
        transpose.setBounds(tk.withTrimmedBottom(26).withSizeKeepingCentre(76, 76).withY(tk.getY() + 2));
        r.removeFromLeft(10);
        // display
        displayArea = r.removeFromLeft(214).toFloat().withSizeKeepingCentre(214, 84).withY((float) r.getY() + 6);
        r.removeFromLeft(10);
        // MIX, LEVEL
        auto mk = r.removeFromLeft(78);  mix.setBounds(mk.withHeight(50).withSizeKeepingCentre(48, 48).withY(mk.getY() + 2));
        auto lk = r.removeFromLeft(78);  level.setBounds(lk.withHeight(50).withSizeKeepingCentre(48, 48).withY(lk.getY() + 2));
        r.removeFromLeft(4);
        // LIVE/STUDIO mini toggle
        auto md = r.removeFromLeft(jmax(60, r.getWidth()));
        mode.setBounds(md.withSizeKeepingCentre(26, 40).withY(md.getY() + 18));
    }

private:
    juce::AudioProcessorValueTreeState& state;
    std::function<int()> studioLatency;
    StompKnobLookAndFeel knobLook;
    juce::Slider transpose, mix, level;
    Footswitch onSwitch;
    MiniToggle mode;
    std::unique_ptr<juce::AudioProcessorValueTreeState::SliderAttachment> tAtt, mAtt, lAtt;
    std::unique_ptr<juce::AudioProcessorValueTreeState::ButtonAttachment> onAtt, modeAtt;
    juce::Rectangle<float> titleArea, ledArea, displayArea;
    float lastT = -99.0f, lastOn = -1.0f, lastMode = -1.0f, lastMix = -1.0f, lastLevel = -99.0f;

    double sampleRate() const { return state.processor.getSampleRate(); }
    void timerCallback() override
    {
        // repaint on any change (mouse or host automation)
        const float t = state.getRawParameterValue("gx_transpose")->load(), on = state.getRawParameterValue("gx_on")->load(),
                    md = state.getRawParameterValue("gx_studio")->load(), mx = state.getRawParameterValue("gx_mix")->load(),
                    lv = state.getRawParameterValue("gx_level")->load();
        auto differs = [](float a, float b) { return std::abs(a - b) > 1e-6f; };
        if (differs(t, lastT) || differs(on, lastOn) || differs(md, lastMode) || differs(mx, lastMix) || differs(lv, lastLevel))
        { lastT = t; lastOn = on; lastMode = md; lastMix = mx; lastLevel = lv; repaint(); }
    }
    static void drawScrew(juce::Graphics& g, juce::Point<float> c)
    {
        using namespace juce;
        g.setGradientFill(ColourGradient(Colour(0xffb8bcc0), c.x - 4, c.y - 4, Colour(0xff55595e), c.x + 4, c.y + 4, false));
        g.fillEllipse(c.x - 4.0f, c.y - 4.0f, 8.0f, 8.0f);
        g.setColour(Colour(0xff2a2c2e));
        g.drawLine(c.x - 2.6f, c.y - 2.6f, c.x + 2.6f, c.y + 2.6f, 1.1f);
        g.drawLine(c.x - 2.6f, c.y + 2.6f, c.x + 2.6f, c.y - 2.6f, 1.1f);
    }
    static void drawLed(juce::Graphics& g, juce::Rectangle<float> r, bool on)
    {
        using namespace juce;
        if (on)
        {
            g.setGradientFill(ColourGradient(Colour(0x90ff3020), r.getCentreX(), r.getCentreY(), Colour(0x00ff3020), r.getCentreX() + 14, r.getCentreY(), true));
            g.fillEllipse(r.expanded(14.0f));
        }
        g.setColour(Colour(0xff1a1a1a)); g.fillEllipse(r.expanded(1.5f));
        g.setGradientFill(ColourGradient(on ? Colour(0xffffb0a0) : Colour(0xff5a1810), r.getCentreX() - 2, r.getY(),
                                         on ? Colour(0xffe0200f) : Colour(0xff2a0805), r.getCentreX() + 2, r.getBottom(), false));
        g.fillEllipse(r);
    }
    static void drawTicks(juce::Graphics& g, juce::Rectangle<float> k, int n, int major, juce::Colour c)
    {
        using namespace juce;
        const auto ctr = k.getCentre();
        const float R = jmin(k.getWidth(), k.getHeight()) * 0.5f;
        for (int i = 0; i < n; ++i)
        {
            const float a = MathConstants<float>::pi * 1.25f + (float) i / (float) (n - 1) * MathConstants<float>::pi * 1.5f;
            const bool big = (i == major) || i == 0 || i == n - 1;
            const float r0 = R + 2.0f, r1 = R + (big ? 7.0f : 4.5f);
            g.setColour(c.withAlpha(big ? c.getFloatAlpha() : c.getFloatAlpha() * 0.6f));
            g.drawLine(ctr.x + std::sin(a) * r0, ctr.y - std::cos(a) * r0, ctr.x + std::sin(a) * r1, ctr.y - std::cos(a) * r1, big ? 1.6f : 1.0f);
        }
    }
};
