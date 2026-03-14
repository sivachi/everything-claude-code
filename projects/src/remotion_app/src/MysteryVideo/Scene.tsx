import { AbsoluteFill, Audio, Img, staticFile, useCurrentFrame, interpolate, useVideoConfig } from "remotion";
import { Subtitle } from "./Subtitle";

export const Scene: React.FC<{
    image: string;
    audio: string;
    text: string;
    duration: number; // in frames (approx)
}> = ({ image, audio, text, duration }) => {
    const frame = useCurrentFrame();

    // Ken Burns effect: Zoom/Pan
    // Zoom from 1.0 (fit) to 1.15 (slightly zoomed) over the duration
    const scale = interpolate(
        frame,
        [0, duration],
        [1.0, 1.15],
        { extrapolateRight: "clamp" }
    );

    // Transitions (Fade In/Out handled by Sequence in parent or simplistic fade here)
    // We'll just do a simple fade in for the image itself if needed, but usually Sequenced scenes cut or cross-dissolve.
    // Let's rely on parent for cross-dissolve or just hard cut.

    return (
        <AbsoluteFill>
            <AbsoluteFill style={{ overflow: "hidden" }}>
                <Img
                    src={staticFile(image)}
                    style={{
                        position: "absolute",
                        width: "100%",
                        height: "100%",
                        objectFit: "cover",
                        transform: `scale(${scale})`,
                    }}
                />
            </AbsoluteFill>
            <Subtitle text={text} />
            <Audio src={staticFile(audio)} />
        </AbsoluteFill>
    );
};
