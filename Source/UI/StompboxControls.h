#pragma once
#include <juce_gui_basics/juce_gui_basics.h>

// Big black knurled knob with a white pointer line (draws any rotary Slider).
class StompKnobLookAndFeel : public juce::LookAndFeel_V4
{
public:
    void drawRotarySlider(juce::Graphics& g, int x, int y, int w, int h, float pos,
                          float startAngle, float endAngle, juce::Slider&) override
    {
        using namespace juce;
        auto r = Rectangle<float>((float) x, (float) y, (float) w, (float) h).reduced(2.0f);
        r = r.withSizeKeepingCentre(jmin(r.getWidth(), r.getHeight()), jmin(r.getWidth(), r.getHeight()));
        const auto c = r.getCentre();
        const float R = r.getWidth() * 0.5f;
        const float angle = startAngle + pos * (endAngle - startAngle);

        // drop shadow on the enclosure
        g.setColour(Colours::black.withAlpha(0.35f));
        g.fillEllipse(r.translated(1.5f, 3.0f));

        // knurled skirt: dark disc with fine ridges
        g.setGradientFill(ColourGradient(Colour(0xff2a2a2a), c.x, c.y - R, Colour(0xff050505), c.x, c.y + R, false));
        g.fillEllipse(r);
        g.setColour(Colours::white.withAlpha(0.07f));
        for (int i = 0; i < 48; ++i)
        {
            const float a = angle + MathConstants<float>::twoPi * (float) i / 48.0f;
            g.drawLine(c.x + std::sin(a) * R * 0.86f, c.y - std::cos(a) * R * 0.86f,
                       c.x + std::sin(a) * R * 0.99f, c.y - std::cos(a) * R * 0.99f, 1.0f);
        }

        // cap: slightly raised, soft top-left highlight
        auto cap = r.reduced(R * 0.14f);
        g.setGradientFill(ColourGradient(Colour(0xff3a3a3a), cap.getX(), cap.getY(),
                                         Colour(0xff0d0d0d), cap.getRight(), cap.getBottom(), false));
        g.fillEllipse(cap);
        g.setColour(Colours::white.withAlpha(0.10f));
        g.drawEllipse(cap.reduced(0.5f), 1.0f);

        // pointer
        Path p;
        p.addRoundedRectangle(-1.6f, -R * 0.84f, 3.2f, R * 0.5f, 1.4f);
        g.setColour(Colour(0xfff2efe6));
        g.fillPath(p, AffineTransform::rotation(angle).translated(c.x, c.y));
    }
};

// Knob drawn from rendered frames laid out in a grid: `columns` square frames per row,
// left->right then top->bottom; frame 0 = knob fully counter-clockwise.
// (A grid keeps the image under the GPU's texture size limit at high resolution.)
class FilmstripKnobLookAndFeel : public juce::LookAndFeel_V4
{
public:
    FilmstripKnobLookAndFeel(juce::Image framesImage, int columns)
        : image(std::move(framesImage)), cols(juce::jmax(1, columns))
    {
        if (image.isValid())
        {
            frameSize = image.getWidth() / cols;
            rows = frameSize > 0 ? image.getHeight() / frameSize : 0;
            frames = cols * rows;
        }
    }

    void drawRotarySlider(juce::Graphics& g, int x, int y, int w, int h, float pos, float, float, juce::Slider&) override
    {
        if (frames < 1) return;
        const int i = juce::jlimit(0, frames - 1, juce::roundToInt(pos * (float) (frames - 1)));
        g.setImageResamplingQuality(juce::Graphics::highResamplingQuality);
        g.setOpacity(1.0f);
        g.drawImage(image, x, y, w, h, (i % cols) * frameSize, (i / cols) * frameSize, frameSize, frameSize);
    }
private:
    juce::Image image;
    int cols = 1, rows = 0, frameSize = 0, frames = 0;
};

// Rotary knob with a centre detent: a small sticky zone around noon (parameter range 0..1 via the
// attachment, so noon = 0.5). Double-click returns to noon (set by the strip).
class DetentSlider : public juce::Slider
{
public:
    DetentSlider() : juce::Slider(juce::Slider::RotaryVerticalDrag, juce::Slider::NoTextBox) {}
    double snapValue(double v, DragMode) override
    {
        const double mid = getMinimum() + 0.5 * (getMaximum() - getMinimum());
        return std::abs(v - mid) < 0.035 * (getMaximum() - getMinimum()) ? mid : v;
    }
};

// Chrome stomp switch with a hex nut. Toggle state = bypassed (matches the "<id>_bypass" parameter).
class Footswitch : public juce::Button
{
public:
    Footswitch() : juce::Button("Footswitch") { setClickingTogglesState(true); }

    // Optional rendered images; when this returns a valid image it is drawn instead of the vector switch.
    std::function<const juce::Image*(bool down)> imageFor;

    void paintButton(juce::Graphics& g, bool over, bool down) override
    {
        using namespace juce;
        if (imageFor)
            if (auto* img = imageFor(down); img != nullptr && img->isValid())
            {
                g.setImageResamplingQuality(Graphics::highResamplingQuality);
                g.setOpacity(1.0f);
                g.drawImage(*img, getLocalBounds().toFloat());
                return;
            }
        auto r = getLocalBounds().toFloat().reduced(1.0f);
        r = r.withSizeKeepingCentre(jmin(r.getWidth(), r.getHeight()), jmin(r.getWidth(), r.getHeight()));
        const auto c = r.getCentre();
        const float R = r.getWidth() * 0.5f;

        // hex nut
        Path hex;
        for (int i = 0; i < 6; ++i)
        {
            const float a = MathConstants<float>::pi / 6.0f + MathConstants<float>::twoPi * (float) i / 6.0f;
            const Point<float> pt { c.x + std::cos(a) * R, c.y + std::sin(a) * R };
            if (i == 0) hex.startNewSubPath(pt); else hex.lineTo(pt);
        }
        hex.closeSubPath();
        g.setColour(Colours::black.withAlpha(0.35f));
        g.fillPath(hex, AffineTransform::translation(1.5f, 3.0f));
        g.setGradientFill(ColourGradient(Colour(0xffe6e8ea), c.x - R, c.y - R, Colour(0xff8d9196), c.x + R, c.y + R, false));
        g.fillPath(hex);
        g.setColour(Colour(0xff5d6166));
        g.strokePath(hex, PathStrokeType(1.0f));

        // plunger
        auto cap = r.reduced(R * (down ? 0.36f : 0.32f));
        g.setGradientFill(ColourGradient(Colour(0xffffffff), cap.getX(), cap.getY(),
                                         Colour(0xff9a9ea3), cap.getRight(), cap.getBottom(), false));
        g.fillEllipse(cap);
        g.setColour(Colour(0xff6b6f74));
        g.drawEllipse(cap, 1.0f);
        g.setColour(Colours::white.withAlpha(over ? 0.35f : 0.2f));
        g.fillEllipse(cap.reduced(cap.getWidth() * 0.28f).translated(-cap.getWidth() * 0.08f, -cap.getWidth() * 0.08f));
    }
};

// Small chrome bat-handle toggle (e.g. a voicing switch). Toggle state true = lever up = ON.
class MiniToggle : public juce::Button
{
public:
    MiniToggle() : juce::Button("Toggle") { setClickingTogglesState(true); }

    // Optional rendered images (lever up / down); when valid they are drawn instead of the vector toggle.
    std::function<const juce::Image*(bool up)> imageFor;

    void paintButton(juce::Graphics& g, bool over, bool) override
    {
        using namespace juce;
        const bool up = getToggleState();
        if (imageFor)
            if (auto* img = imageFor(up); img != nullptr && img->isValid())
            {
                g.setImageResamplingQuality(Graphics::highResamplingQuality);
                g.setOpacity(1.0f);
                g.drawImage(*img, getLocalBounds().toFloat());
                return;
            }
        auto r = getLocalBounds().toFloat();
        const float w = jmin(r.getWidth(), r.getHeight() * 0.62f);
        const auto c = r.getCentre();
        const float R = w * 0.5f;
        // hex nut + bushing
        Path hex;
        for (int i = 0; i < 6; ++i)
        {
            const float a = MathConstants<float>::twoPi * (float) i / 6.0f;
            const Point<float> pt { c.x + std::cos(a) * R, c.y + std::sin(a) * R };
            if (i == 0) hex.startNewSubPath(pt); else hex.lineTo(pt);
        }
        hex.closeSubPath();
        g.setColour(Colours::black.withAlpha(0.35f));
        g.fillPath(hex, AffineTransform::translation(1.0f, 2.0f));
        g.setGradientFill(ColourGradient(Colour(0xffe6e8ea), c.x - R, c.y - R, Colour(0xff7d8186), c.x + R, c.y + R, false));
        g.fillPath(hex);
        g.setColour(Colour(0xff55595e)); g.strokePath(hex, PathStrokeType(0.8f));
        const float rb = R * 0.55f;
        g.setGradientFill(ColourGradient(Colour(0xfff4f5f6), c.x - rb, c.y - rb, Colour(0xff6b6f74), c.x + rb, c.y + rb, false));
        g.fillEllipse(c.x - rb, c.y - rb, rb * 2, rb * 2);
        // bat lever, seen from above at an angle: tapers towards the tip
        const float len = r.getHeight() * 0.46f, dir = up ? -1.0f : 1.0f;
        const Point<float> tip { c.x, c.y + dir * len };
        Path lever;
        lever.startNewSubPath(c.x - rb * 0.45f, c.y);
        lever.lineTo(tip.x - rb * 0.62f, tip.y);
        lever.lineTo(tip.x + rb * 0.62f, tip.y);
        lever.lineTo(c.x + rb * 0.45f, c.y);
        lever.closeSubPath();
        g.setColour(Colours::black.withAlpha(0.35f));
        g.fillPath(lever, AffineTransform::translation(1.5f, 2.5f));
        g.setGradientFill(ColourGradient(Colour(0xffffffff), c.x - rb, c.y, Colour(0xff8d9196), c.x + rb, c.y, false));
        g.fillPath(lever);
        g.fillEllipse(tip.x - rb * 0.68f, tip.y - rb * 0.68f, rb * 1.36f, rb * 1.36f);
        g.setColour(Colour(0xff5d6166));
        g.strokePath(lever, PathStrokeType(0.7f));
        if (over) { g.setColour(Colours::white.withAlpha(0.12f)); g.fillEllipse(r.reduced(1.0f)); }
    }
};

// Three-position mini toggle (lever up / centre / down), e.g. Night Courier's DELAY / REVERB / BOTH.
// Click the upper half to move the lever up one position, the lower half to move it down; the mouse wheel works too.
// Position 0 = up, 1 = centre, 2 = down (= PedalBase::togglePositions == 3 choice parameter).
class ThreeWayToggle : public juce::Component, public juce::SettableTooltipClient
{
public:
    std::function<void(int)> onChange;                          // user moved the lever
    std::function<const juce::Image*(int pos)> imageFor;        // optional rendered images per position
    int getPosition() const { return pos; }
    void setPosition(int p) { p = juce::jlimit(0, 2, p); if (p != pos) { pos = p; repaint(); } }

    void mouseDown(const juce::MouseEvent& e) override { move(e.position.y < (float) getHeight() * 0.5f ? -1 : 1); }
    void mouseWheelMove(const juce::MouseEvent&, const juce::MouseWheelDetails& w) override { if (w.deltaY != 0.0f) move(w.deltaY > 0 ? -1 : 1); }

    void paint(juce::Graphics& g) override
    {
        using namespace juce;
        if (imageFor)
            if (auto* img = imageFor(pos); img != nullptr && img->isValid())
            {
                g.setImageResamplingQuality(Graphics::highResamplingQuality);
                g.setOpacity(1.0f);
                g.drawImage(*img, getLocalBounds().toFloat());
                return;
            }
        auto r = getLocalBounds().toFloat();
        const float R = jmin(r.getWidth(), r.getHeight() * 0.62f) * 0.5f;
        const auto c = r.getCentre();
        Path hex;
        for (int i = 0; i < 6; ++i)
        {
            const float a = MathConstants<float>::twoPi * (float) i / 6.0f;
            const Point<float> pt { c.x + std::cos(a) * R, c.y + std::sin(a) * R };
            if (i == 0) hex.startNewSubPath(pt); else hex.lineTo(pt);
        }
        hex.closeSubPath();
        g.setColour(Colours::black.withAlpha(0.35f)); g.fillPath(hex, AffineTransform::translation(1.0f, 2.0f));
        g.setGradientFill(ColourGradient(Colour(0xffe6e8ea), c.x - R, c.y - R, Colour(0xff7d8186), c.x + R, c.y + R, false));
        g.fillPath(hex);
        const float rb = R * 0.55f;
        g.setGradientFill(ColourGradient(Colour(0xfff4f5f6), c.x - rb, c.y - rb, Colour(0xff6b6f74), c.x + rb, c.y + rb, false));
        g.fillEllipse(c.x - rb, c.y - rb, rb * 2, rb * 2);
        // lever: up / centre (pointing at the viewer: short) / down
        const float len = pos == 1 ? r.getHeight() * 0.10f : r.getHeight() * 0.46f, dir = pos == 2 ? 1.0f : -1.0f;
        const Point<float> tip { c.x, c.y + dir * len };
        g.setGradientFill(ColourGradient(Colour(0xffffffff), c.x - rb, c.y, Colour(0xff8d9196), c.x + rb, c.y, false));
        Path lever;
        lever.startNewSubPath(c.x - rb * 0.45f, c.y); lever.lineTo(tip.x - rb * 0.62f, tip.y);
        lever.lineTo(tip.x + rb * 0.62f, tip.y); lever.lineTo(c.x + rb * 0.45f, c.y); lever.closeSubPath();
        g.fillPath(lever);
        g.fillEllipse(tip.x - rb * 0.68f, tip.y - rb * 0.68f, rb * 1.36f, rb * 1.36f);
    }

private:
    int pos = 2;
    void move(int d)
    {
        const int p = juce::jlimit(0, 2, pos + d);
        if (p == pos) return;
        pos = p; repaint();
        if (onChange) onChange(pos);
    }
};
