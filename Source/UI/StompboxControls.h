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
