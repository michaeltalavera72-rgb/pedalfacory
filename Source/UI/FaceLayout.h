#pragma once
#include <juce_gui_basics/juce_gui_basics.h>

// Where everything sits on a stompbox face. Computed from the body rectangle so the
// face painter (graphics) and PedalStrip::resized (knob/footswitch components) agree.
struct FaceLayout
{
    // Pedal body proportions (226 x 372 px since v28; was 226 x 298). Blender faces are rendered at this shape;
    // a face image with a different shape is ignored (the vector face is shown) until it is re-rendered.
    static constexpr float bodyAspect = 372.0f / 226.0f;
    // Gatekeeper's printed artwork is inset 2.6 mm on the 91 mm-wide body.
    static constexpr float artInset = 2.6f / 91.0f;

    juce::Rectangle<float> body;               // the whole enclosure
    juce::Array<juce::Rectangle<float>> knobs; // one square per knob, left to right
    juce::Array<juce::Rectangle<float>> labels;// text under each knob
    juce::Rectangle<float> name, subtitle, emblem, led, footswitch;
    // Pedals with two footswitches (e.g. drive + boost): switches at 29% / 71% of the width,
    // an LED above each and a small printed label above each LED. Single-switch layout unchanged.
    bool twoSwitches = false;
    juce::Rectangle<float> led2, footswitch2, switchLabel1, switchLabel2;
    bool secondaryOn = false;            // state of the second LED, filled in by the strip
    // Optional mini toggle (PedalBase::toggleId), with its printed label above it.
    bool hasToggle = false;
    juce::Rectangle<float> toggle, toggleLabel;
    juce::Rectangle<float> window;           // optional second artwork area (Slow Burn: the valve window)

    static FaceLayout make(juce::Rectangle<float> body, int numKnobs, int numSwitches = 1, bool withToggle = false)
    {
        FaceLayout f; f.body = body;
        const float W = body.getWidth(), H = body.getHeight(), x0 = body.getX(), y0 = body.getY();
        // 1-3 knobs: big knobs spread over 19%..81% of the width (Ramhorn renders depend on this).
        // 4+ knobs: smaller knobs spread over 15%..85%.
        const bool wide = numKnobs >= 4;
        const float d = W * (wide ? 0.19f : 0.255f);         // knob diameter
        const float span0 = wide ? 0.15f : 0.19f, span = wide ? 0.70f : 0.62f;
        const float knobTop = y0 + H * 0.055f;
        for (int i = 0; i < numKnobs; ++i)
        {
            const float cx = x0 + W * (numKnobs == 1 ? 0.5f : span0 + span * (float) i / (float) (numKnobs - 1));
            f.knobs.add({ cx - d * 0.5f, knobTop, d, d });
            f.labels.add({ cx - d * 0.75f, knobTop + d + 3.0f, d * 1.5f, 13.0f });
        }
        f.name     = { x0 + W * 0.06f, y0 + H * 0.355f, W * 0.88f, H * 0.135f };
        f.subtitle = { x0 + W * 0.06f, y0 + H * 0.49f,  W * 0.88f, H * 0.065f };
        f.emblem   = { x0 + W * 0.26f, y0 + H * 0.565f, W * 0.48f, H * 0.135f };
        const float sw = W * 0.19f;
        f.footswitch = { x0 + (W - sw) * 0.5f, y0 + H * 0.865f - sw * 0.5f, sw, sw };
        f.led = juce::Rectangle<float>(11.0f, 11.0f).withCentre({ x0 + W * 0.5f, y0 + H * 0.74f });
        if (numKnobs == 6)
        {
            // Two rows of three: big knobs on top, small knobs below (like the 16 mm / 9 mm pots of the
            // real thing). Below them (Feral Hound): a big square artwork as the "emblem" with the name
            // printed across its top, the footswitch a little lower, the LED to its right and the
            // subtitle to its left.
            f.knobs.clear(); f.labels.clear();
            const float d1 = W * 0.215f, d2 = W * 0.15f, top1 = y0 + H * 0.045f, top2 = y0 + H * 0.262f;
            for (int i = 0; i < 6; ++i)
            {
                const bool big = i < 3;
                const float d = big ? d1 : d2, top = big ? top1 : top2;
                const float cx = x0 + W * (0.22f + 0.28f * (float) (i % 3));
                f.knobs.add({ cx - d * 0.5f, top, d, d });
                f.labels.add({ cx - W * 0.14f, top + d + 1.0f, W * 0.28f, 13.0f });
            }
            f.name     = { x0 + W * 0.06f, y0 + H * 0.425f, W * 0.88f, H * 0.10f };
            f.emblem   = juce::Rectangle<float>(W * 0.66f, W * 0.66f).withCentre({ x0 + W * 0.5f, y0 + H * 0.64f });
            f.footswitch = juce::Rectangle<float>(sw, sw).withCentre({ x0 + W * 0.5f, y0 + H * 0.905f });
            f.led      = juce::Rectangle<float>(11.0f, 11.0f).withCentre({ x0 + W * 0.80f, y0 + H * 0.905f });
            f.subtitle = juce::Rectangle<float>(W * 0.30f, H * 0.04f).withCentre({ x0 + W * 0.205f, y0 + H * 0.905f });
        }
        if (numKnobs == 6 && withToggle)
        {
            // Slow Burn: same two knob rows; below them the printed artwork (left, 2:3, carries the name) and
            // the valve standing upright in a tall window (right), the subtitle under the window, and a bottom
            // row of DEEP toggle / footswitch / LED.
            f.emblem   = juce::Rectangle<float>(W * 0.40f, W * 0.60f).withCentre({ x0 + W * 0.29f, y0 + H * 0.60f });   // 2:3 art
            f.name     = f.emblem;                                       // the artwork's lettering is the name
            f.window   = juce::Rectangle<float>(W * 0.22f, W * 0.56f).withCentre({ x0 + W * 0.73f, y0 + H * 0.60f });
            f.subtitle = juce::Rectangle<float>(W * 0.40f, H * 0.030f).withCentre({ x0 + W * 0.73f, y0 + H * 0.795f });
            f.footswitch = juce::Rectangle<float>(sw, sw).withCentre({ x0 + W * 0.5f, y0 + H * 0.895f });
            f.led      = juce::Rectangle<float>(11.0f, 11.0f).withCentre({ x0 + W * 0.80f, y0 + H * 0.895f });
            f.hasToggle = true;
            f.toggle      = juce::Rectangle<float>(W * 0.10f, W * 0.16f).withCentre({ x0 + W * 0.20f, y0 + H * 0.905f });
            f.toggleLabel = juce::Rectangle<float>(W * 0.24f, H * 0.032f).withCentre({ x0 + W * 0.20f, y0 + H * 0.812f });
        }
        if (numKnobs == 2 && withToggle)
        {
            // Gatekeeper: Michael's full-face artwork, printed 2.6 mm (artInset of W) inside the enclosure edge.
            // Every control sits exactly over the one painted in the art (= render_gatekeeper.py / make_gatekeeper_art.py).
            f.knobs.clear(); f.labels.clear();
            const float dk = W * 0.235f;
            for (float cxf : { 0.1787f, 0.8246f })
            {
                const auto k = juce::Rectangle<float>(dk, dk).withCentre({ x0 + W * cxf, y0 + H * 0.1223f });
                f.knobs.add(k);
                f.labels.add({ k.getX(), k.getBottom(), dk, 13.0f });      // printed in the art; unused
            }
            f.emblem   = body.reduced(W * artInset);
            f.name     = f.emblem;                                         // the artwork carries name + labels
            f.subtitle = {};
            f.led      = juce::Rectangle<float>(11.0f, 11.0f).withCentre({ x0 + W * 0.50f, y0 + H * 0.7217f });
            f.footswitch = juce::Rectangle<float>(sw, sw).withCentre({ x0 + W * 0.50f, y0 + H * 0.8148f });
            f.hasToggle = true;
            f.toggle      = juce::Rectangle<float>(W * 0.10f, W * 0.16f).withCentre({ x0 + W * 0.23f, y0 + H * 0.8148f });
            f.toggleLabel = juce::Rectangle<float>(W * 0.20f, H * 0.03f).withCentre({ x0 + W * 0.23f, y0 + H * 0.752f });
        }
        if (numSwitches >= 2)
        {
            f.twoSwitches = true;
            const float cx1 = x0 + W * 0.29f, cx2 = x0 + W * 0.71f;
            f.footswitch  = juce::Rectangle<float>(sw, sw).withCentre({ cx1, y0 + H * 0.865f });
            f.footswitch2 = juce::Rectangle<float>(sw, sw).withCentre({ cx2, y0 + H * 0.865f });
            f.led  = juce::Rectangle<float>(11.0f, 11.0f).withCentre({ cx1, y0 + H * 0.745f });
            f.led2 = juce::Rectangle<float>(11.0f, 11.0f).withCentre({ cx2, y0 + H * 0.745f });
            f.switchLabel1 = { cx1 - W * 0.13f, y0 + H * 0.675f, W * 0.26f, H * 0.04f };
            f.switchLabel2 = { cx2 - W * 0.13f, y0 + H * 0.675f, W * 0.26f, H * 0.04f };
            f.emblem = { x0 + W * 0.38f, y0 + H * 0.57f, W * 0.24f, H * 0.12f };   // narrower: labels sit beside it
        }
        return f;
    }
};
