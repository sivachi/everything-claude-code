import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

export const SimpleHelloWorld: React.FC = () => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();

    // フェードインアニメーション: 0秒から2秒かけて opacity を 0 → 1 に
    const opacity = interpolate(
        frame,
        [0, 2 * fps], // 0フレーム〜60フレーム（2秒）
        [0, 1],
        {
            extrapolateRight: "clamp", // 2秒以降は opacity 1 を維持
        }
    );

    return (
        <AbsoluteFill
            style={{
                backgroundColor: "white",
                justifyContent: "center",
                alignItems: "center",
            }}
        >
            <div
                style={{
                    opacity,
                    fontSize: 100,
                    fontWeight: "bold",
                    color: "black",
                    textAlign: "center",
                }}
            >
                動画制作スタート！
            </div>
        </AbsoluteFill>
    );
};
