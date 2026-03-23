import { AbsoluteFill, Sequence, useVideoConfig, useCurrentFrame, interpolate } from "remotion";
import { Scene } from "./Scene";

const FadingScene: React.FC<{
    index: number;
    totalScenes: number;
    transitionDuration: number;
    image: string;
    audio: string;
    text: string;
    duration: number;
}> = ({ index, totalScenes, transitionDuration, ...sceneProps }) => {
    const frame = useCurrentFrame();
    const { durationInFrames } = useVideoConfig();

    const fadeIn = index > 0
        ? interpolate(frame, [0, transitionDuration], [0, 1], { extrapolateRight: "clamp" })
        : 1;

    const fadeOut = index < totalScenes - 1
        ? interpolate(frame, [durationInFrames - transitionDuration, durationInFrames], [1, 0], { extrapolateRight: "clamp" })
        : 1;

    return (
        <AbsoluteFill style={{ opacity: fadeIn * fadeOut }}>
            <Scene {...sceneProps} />
        </AbsoluteFill>
    );
};

// Audio durations: scene1=10.40s, scene2=13.56s, scene3=10.22s, scene4=12.07s
// At 30fps + ~18 frame padding each
const SCENES = [
    {
        id: "scene1",
        text: "ようこそ、今宵の「謎会」へ。私たちは、歴史の教科書が決して語らない「隙間」にある真実を探求する集まりです。",
        image: "mystery-assets/scene1.jpg",
        audio: "mystery-assets/scene1.mp3",
        duration: 330, // 10.40s × 30 = 312 + 18
    },
    {
        id: "scene2",
        text: "皆さん、「アトランティス」という言葉を聞いて、何を思い浮かべますか？海に沈んだ幻の都市？プラトンが描いたおとぎ話？それとも、ハリウッド映画のファンタジーでしょうか。",
        image: "mystery-assets/scene2.jpg",
        audio: "mystery-assets/scene2.mp3",
        duration: 425, // 13.56s × 30 = 407 + 18
    },
    {
        id: "scene3",
        text: "もし、アトランティスが「海に沈んでいない」としたら？もし、彼らが持っていたテクノロジーが、機械ではなく「精神（スピリチュアル）」によるものだったとしたら？",
        image: "mystery-assets/scene3.jpg",
        audio: "mystery-assets/scene3.mp3",
        duration: 325, // 10.22s × 30 = 307 + 18
    },
    {
        id: "scene4",
        text: "今日は、1万2000年前の記憶を呼び覚ます旅に出かけましょう。準備はいいですか？ 深呼吸をしてください。常識という名の重りを、今ここで捨ててしまいましょう。",
        image: "mystery-assets/scene4.jpg",
        audio: "mystery-assets/scene4.mp3",
        duration: 380, // 12.07s × 30 = 362 + 18
    },
];

const TRANSITION_DURATION = 30; // 1 second cross-fade

export const MysteryVideo: React.FC = () => {
    return (
        <AbsoluteFill style={{ backgroundColor: "black" }}>
            {SCENES.map((scene, index) => {
                let from = 0;
                for (let i = 0; i < index; i++) {
                    from += SCENES[i].duration - TRANSITION_DURATION;
                }

                return (
                    <Sequence key={scene.id} from={from} durationInFrames={scene.duration}>
                        <FadingScene
                            {...scene}
                            index={index}
                            totalScenes={SCENES.length}
                            transitionDuration={TRANSITION_DURATION}
                        />
                    </Sequence>
                );
            })}
            {/* Title overlay */}
            <Sequence from={0} durationInFrames={120}>
                <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
                    <div style={{
                        color: "white",
                        fontSize: 120,
                        fontWeight: "bold",
                        fontFamily: "'Noto Sans JP', 'Hiragino Sans', system-ui, sans-serif",
                        textShadow: "0 0 30px rgba(0,0,0,0.9), 0 0 60px rgba(0,0,0,0.5)",
                        letterSpacing: 20,
                        opacity: interpolate(
                            useCurrentFrame(),
                            [0, 30, 90, 120],
                            [0, 1, 1, 0],
                            { extrapolateRight: "clamp" }
                        ),
                    }}>
                        謎会
                    </div>
                </AbsoluteFill>
            </Sequence>
        </AbsoluteFill>
    );
};
