import { AbsoluteFill, Sequence, useVideoConfig, useCurrentFrame, interpolate } from "remotion";
import { Scene } from "./Scene";

// Approx duration of audio files - normally we'd measure them, but for MVP we estimate or hardcode based on generation length or assume ~30fps * seconds.
// For a robust app, we'd use `getAudioDurationInSeconds` script or similar metadata.
// Since we generated them, let's estimate:
// Scene 1: ~10s
// Scene 2: ~15s
// Scene 3: ~12s
// Scene 4: ~15s
// Total ~ 52s

// We will use 10 sec blocks for simplicity in this MVP iteration, adjusted slightly manually.

// FadingScene component to handle opacity
const FadingScene: React.FC<any> = ({ index, totalScenes, transitionDuration, ...props }) => {
    const frame = useCurrentFrame();
    const { durationInFrames } = useVideoConfig(); // use local duration

    // Fade in (if not first scene)
    const fadeIn = index > 0 ? interpolate(
        frame,
        [0, transitionDuration],
        [0, 1],
        { extrapolateRight: "clamp" }
    ) : 1;

    // Fade out (if not last scene)
    const fadeOut = index < totalScenes - 1 ? interpolate(
        frame,
        [durationInFrames - transitionDuration, durationInFrames],
        [1, 0],
        { extrapolateRight: "clamp" }
    ) : 1;

    return (
        <AbsoluteFill style={{ opacity: fadeIn * fadeOut }}>
            <Scene {...props} />
        </AbsoluteFill>
    );
};

const SCENES = [
    {
        id: "scene1",
        text: "ようこそ、今宵の「謎会」へ。私たちは、歴史の教科書が決して語らない「隙間」にある真実を探求する集まりです。",
        image: "mystery-assets/scene1.jpg",
        audio: "mystery-assets/scene1.mp3",
        duration: 350,
    },
    {
        id: "scene2",
        text: "皆さん、「アトランティス」という言葉を聞いて、何を思い浮かべますか？海に沈んだ幻の都市？プラトンが描いたおとぎ話？それとも、ハリウッド映画のファンタジーでしょうか。",
        image: "mystery-assets/scene2.jpg",
        audio: "mystery-assets/scene2.mp3",
        duration: 450,
    },
    {
        id: "scene3",
        text: "もし、アトランティスが「海に沈んでいない」としたら？もし、彼らが持っていたテクノロジーが、機械ではなく「精神（スピリチュアル）」によるものだったとしたら？",
        image: "mystery-assets/scene3.jpg",
        audio: "mystery-assets/scene3.mp3",
        duration: 400,
    },
    {
        id: "scene4",
        text: "今日は、1万2000年前の記憶を呼び覚ます旅に出かけましょう。準備はいいですか？ 深呼吸をしてください。常識という名の重りを、今ここで捨ててしまいましょう。",
        image: "mystery-assets/scene4.jpg",
        audio: "mystery-assets/scene4.mp3",
        duration: 450,
    }
];

export const MysteryVideo: React.FC = () => {
    let currentFrame = 0;

    return (
        <AbsoluteFill style={{ backgroundColor: "black" }}>
            {SCENES.map((scene, index) => {
                // Determine start frame for this scene
                // Previous scenes total duration minus overlap for crossfading
                // We want 1 second fade (30 frames)
                const transitionDuration = 30;

                // Calculate start time based on previous scenes
                // If index 0, start at 0.
                // If index > 0, start at (previous_scene_end - transitionDuration)
                // But simplified: 
                // We need to track cumulative time allowing for overlap.
                // Let's re-calculate absolute start times.

                const prevDuration = SCENES.slice(0, index).reduce((acc, s) => acc + s.duration, 0);
                // For each previous scene (except the first one?), we subtract transitionDuration?
                // Actually, if we want cross dissolve, scene N starts, scene N+1 starts at (Scene N end - 30).

                // Let's do a simple calculation:
                // Scene 0 starts at 0. Ends at duration.
                // Scene 1 starts at Scene 0 duration - 30.
                // Scene 2 starts at Scene 1 start + Scene 1 duration - 30.

                let from = 0;
                for (let i = 0; i < index; i++) {
                    from += SCENES[i].duration - (i < SCENES.length - 1 ? transitionDuration : 0);
                }

                // We need to pass the fade configuration to Scene or handle it here?
                // Scene component handles internal elements, but for cross fade the container needs opacity?
                // Or we can just use `Transition` component from remotion-transitions (not installed),
                // or simpler: just opacity on the sequence or a wrapper div.
                // Remotion Sequence doesn't have opacity prop. Use AbsoluteFill and interpolate.

                return (
                    <Sequence key={scene.id} from={from} durationInFrames={scene.duration}>
                        <FadingScene
                            {...scene}
                            index={index}
                            totalScenes={SCENES.length}
                            transitionDuration={transitionDuration}
                        />
                    </Sequence>
                );
            })}
            {/* Logo overlay for intro */}
            <Sequence from={0} durationInFrames={150}>
                <div style={{
                    position: 'absolute',
                    top: '20%',
                    left: 0,
                    width: '100%',
                    textAlign: 'center',
                    color: 'white',
                    fontSize: 120,
                    fontWeight: 'bold',
                    textShadow: '0 0 20px black',
                    opacity: 0.8
                }}>
                    謎会
                </div>
            </Sequence>
        </AbsoluteFill>
    );
};
