import { AbsoluteFill, Audio, Img, staticFile, useCurrentFrame, interpolate } from "remotion";
import { Subtitle } from "./Subtitle";

export const Scene: React.FC<{
    image: string;
    audio: string;
    text: string;
    duration: number;
}> = ({ image, audio, text, duration }) => {
    const frame = useCurrentFrame();

    // Ken Burns: zoom 1.0 → 1.15 with subtle pan
    const scale = interpolate(frame, [0, duration], [1.0, 1.15], { extrapolateRight: "clamp" });
    const translateX = interpolate(frame, [0, duration], [0, -15], { extrapolateRight: "clamp" });
    const translateY = interpolate(frame, [0, duration], [0, -8], { extrapolateRight: "clamp" });

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
                        transform: `scale(${scale}) translate(${translateX}px, ${translateY}px)`,
                    }}
                />
            </AbsoluteFill>
            <Subtitle text={text} />
            <Audio src={staticFile(audio)} />
        </AbsoluteFill>
    );
};
