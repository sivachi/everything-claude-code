import { AbsoluteFill, Img, staticFile, useCurrentFrame, interpolate, useVideoConfig } from "remotion";

export const ProfessionalVideo: React.FC = () => {
    const frame = useCurrentFrame();
    const { durationInFrames } = useVideoConfig();

    // Ken Burns effect: Zoom in slightly from 1.0 to 1.1
    const scale = interpolate(
        frame,
        [0, durationInFrames],
        [1.0, 1.1],
        {
            extrapolateRight: "clamp",
        }
    );

    // Text fade in
    const opacity = interpolate(
        frame,
        [0, 30],
        [0, 1],
        {
            extrapolateRight: "clamp",
        }
    );

    // Text move up slightly
    const translateY = interpolate(
        frame,
        [0, 30],
        [20, 0],
        {
            extrapolateRight: "clamp",
        }
    );

    return (
        <AbsoluteFill style={{ backgroundColor: "black" }}>
            <AbsoluteFill style={{ overflow: "hidden" }}>
                <Img
                    src={staticFile("S__2768900.jpg")}
                    style={{
                        position: "absolute",
                        width: "100%",
                        height: "100%",
                        objectFit: "cover",
                        transform: `scale(${scale})`,
                    }}
                />
            </AbsoluteFill>

            <AbsoluteFill
                style={{
                    justifyContent: "flex-end",
                    alignItems: "center",
                    paddingBottom: 100,
                }}
            >
                <div
                    style={{
                        color: "white",
                        fontSize: 80,
                        fontWeight: "bold",
                        fontFamily: "'Noto Sans JP', 'Hiragino Sans', 'Yu Gothic', system-ui, sans-serif",
                        textAlign: "center",
                        textShadow: "0 2px 8px rgba(0,0,0,0.8), 0 0 20px rgba(0,0,0,0.4)",
                        opacity,
                        transform: `translateY(${translateY}px)`,
                    }}
                >
                    本格的な動画制作
                </div>
                <div
                    style={{
                        color: "white",
                        fontSize: 40,
                        fontWeight: "normal",
                        fontFamily: "'Noto Sans JP', 'Hiragino Sans', 'Yu Gothic', system-ui, sans-serif",
                        textAlign: "center",
                        marginTop: 20,
                        textShadow: "1px 1px 0 #000",
                        opacity,
                        transform: `translateY(${translateY}px)`,
                    }}
                >
                    Remotionで自動生成
                </div>
            </AbsoluteFill>
            {/* 
                Placeholder for Audio. 
                If you have an audio file, say "bgm.mp3" in public folder:
                <Audio src={staticFile("bgm.mp3")} />
            */}
        </AbsoluteFill>
    );
};
