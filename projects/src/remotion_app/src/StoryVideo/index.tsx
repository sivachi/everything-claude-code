import { AbsoluteFill, Sequence, useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";

// Instagram Story: 1080x1920, 15秒, 30fps = 450フレーム

const BG_COLOR = "#0a0a1a";
const ACCENT = "#c9a84c";
const TEXT_COLOR = "#ffffff";
const FONT = "'Noto Sans JP', 'Hiragino Sans', system-ui, sans-serif";

// --- シーン1: フック（0〜3秒）---
const HookScene: React.FC = () => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();

    const titleOpacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });
    const numberScale = spring({ frame: frame - 15, fps, config: { damping: 12, stiffness: 150 } });
    const numberOpacity = interpolate(frame, [15, 25], [0, 1], { extrapolateRight: "clamp" });
    const subtitleOpacity = interpolate(frame, [50, 65], [0, 1], { extrapolateRight: "clamp" });

    return (
        <AbsoluteFill style={{
            background: `radial-gradient(ellipse at center, #1a1a3a 0%, ${BG_COLOR} 70%)`,
            justifyContent: "center",
            alignItems: "center",
        }}>
            {/* 問いかけ */}
            <div style={{
                position: "absolute",
                top: 380,
                width: "100%",
                textAlign: "center",
                opacity: titleOpacity,
            }}>
                <div style={{
                    fontSize: 52,
                    color: TEXT_COLOR,
                    fontFamily: FONT,
                    fontWeight: 300,
                    letterSpacing: 4,
                }}>
                    あなたの守護霊は
                </div>
            </div>

            {/* 数字「20」 */}
            <div style={{
                position: "absolute",
                top: 520,
                width: "100%",
                textAlign: "center",
                opacity: numberOpacity,
                transform: `scale(${numberScale})`,
            }}>
                <span style={{
                    fontSize: 280,
                    fontWeight: 900,
                    color: ACCENT,
                    fontFamily: FONT,
                    textShadow: `0 0 60px ${ACCENT}66, 0 0 120px ${ACCENT}33`,
                }}>
                    20
                </span>
                <span style={{
                    fontSize: 80,
                    color: TEXT_COLOR,
                    fontFamily: FONT,
                    fontWeight: 400,
                    marginLeft: 10,
                }}>
                    人
                </span>
            </div>

            {/* サブタイトル */}
            <div style={{
                position: "absolute",
                top: 880,
                width: "100%",
                textAlign: "center",
                opacity: subtitleOpacity,
            }}>
                <div style={{
                    fontSize: 42,
                    color: "#aaaacc",
                    fontFamily: FONT,
                    fontWeight: 300,
                }}>
                    知っていましたか？
                </div>
            </div>
        </AbsoluteFill>
    );
};

// --- シーン2: チーム構造（3〜7秒）---
const TeamScene: React.FC = () => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();

    const titleOpacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });

    const items = [
        "24時間365日、あなた専属",
        "状況に応じて担当が交代",
        "補助霊を含む組織的なチーム",
    ];

    return (
        <AbsoluteFill style={{
            background: `linear-gradient(180deg, #0d0d2b 0%, #1a1a3a 50%, #0d0d2b 100%)`,
            justifyContent: "center",
            alignItems: "center",
        }}>
            <div style={{
                position: "absolute",
                top: 350,
                width: "100%",
                textAlign: "center",
                opacity: titleOpacity,
            }}>
                <div style={{
                    fontSize: 56,
                    color: ACCENT,
                    fontFamily: FONT,
                    fontWeight: 700,
                    letterSpacing: 6,
                }}>
                    チームで動いている
                </div>
            </div>

            <div style={{
                position: "absolute",
                top: 520,
                width: "100%",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 40,
            }}>
                {items.map((item, i) => {
                    const delay = 20 + i * 25;
                    const itemOpacity = interpolate(frame, [delay, delay + 15], [0, 1], { extrapolateRight: "clamp" });
                    const slideUp = interpolate(frame, [delay, delay + 15], [30, 0], { extrapolateRight: "clamp" });

                    return (
                        <div key={i} style={{
                            opacity: itemOpacity,
                            transform: `translateY(${slideUp}px)`,
                            display: "flex",
                            alignItems: "center",
                            gap: 20,
                        }}>
                            <div style={{
                                width: 12,
                                height: 12,
                                borderRadius: "50%",
                                backgroundColor: ACCENT,
                                boxShadow: `0 0 10px ${ACCENT}88`,
                            }} />
                            <div style={{
                                fontSize: 44,
                                color: TEXT_COLOR,
                                fontFamily: FONT,
                                fontWeight: 400,
                            }}>
                                {item}
                            </div>
                        </div>
                    );
                })}
            </div>

            <div style={{
                position: "absolute",
                bottom: 500,
                width: "100%",
                textAlign: "center",
                opacity: interpolate(frame, [90, 105], [0, 1], { extrapolateRight: "clamp" }),
            }}>
                <div style={{
                    fontSize: 38,
                    color: "#8888aa",
                    fontFamily: FONT,
                    fontWeight: 300,
                    lineHeight: 1.8,
                }}>
                    1人じゃない。{"\n"}
                    あなた専属のプロジェクトチーム。
                </div>
            </div>
        </AbsoluteFill>
    );
};

// --- シーン3: 予告（7〜12秒）---
const TeaserScene: React.FC = () => {
    const frame = useCurrentFrame();

    const items = [
        { icon: "🌙", text: "夢にはメッセージがある" },
        { icon: "🫀", text: "体の左右で意味が違う" },
        { icon: "💍", text: "結婚で半分入れ替わる" },
        { icon: "😢", text: "守護霊にも感情がある" },
    ];

    const titleOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });

    return (
        <AbsoluteFill style={{
            background: `radial-gradient(ellipse at top, #1a1a3a 0%, ${BG_COLOR} 70%)`,
            justifyContent: "center",
            alignItems: "center",
        }}>
            <div style={{
                position: "absolute",
                top: 300,
                width: "100%",
                textAlign: "center",
                opacity: titleOpacity,
            }}>
                <div style={{
                    fontSize: 44,
                    color: ACCENT,
                    fontFamily: FONT,
                    fontWeight: 600,
                    letterSpacing: 4,
                }}>
                    まだまだ謎がある
                </div>
            </div>

            <div style={{
                position: "absolute",
                top: 440,
                width: "100%",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 36,
                padding: "0 80px",
            }}>
                {items.map((item, i) => {
                    const delay = 15 + i * 22;
                    const itemOpacity = interpolate(frame, [delay, delay + 12], [0, 1], { extrapolateRight: "clamp" });
                    const slideLeft = interpolate(frame, [delay, delay + 12], [40, 0], { extrapolateRight: "clamp" });

                    return (
                        <div key={i} style={{
                            opacity: itemOpacity,
                            transform: `translateX(${slideLeft}px)`,
                            display: "flex",
                            alignItems: "center",
                            gap: 24,
                            width: "100%",
                        }}>
                            <span style={{ fontSize: 48 }}>{item.icon}</span>
                            <div style={{
                                fontSize: 40,
                                color: TEXT_COLOR,
                                fontFamily: FONT,
                                fontWeight: 400,
                            }}>
                                {item.text}
                            </div>
                        </div>
                    );
                })}
            </div>

            <div style={{
                position: "absolute",
                bottom: 480,
                width: "100%",
                textAlign: "center",
                opacity: interpolate(frame, [100, 115], [0, 1], { extrapolateRight: "clamp" }),
            }}>
                <div style={{
                    fontSize: 36,
                    color: "#8888aa",
                    fontFamily: FONT,
                    fontStyle: "italic",
                }}>
                    詳しくはnoteで →
                </div>
            </div>
        </AbsoluteFill>
    );
};

// --- シーン4: CTA（12〜15秒）---
const CTAScene: React.FC = () => {
    const frame = useCurrentFrame();
    const { fps } = useVideoConfig();

    const logoScale = spring({ frame, fps, config: { damping: 10, stiffness: 100 } });
    const textOpacity = interpolate(frame, [20, 35], [0, 1], { extrapolateRight: "clamp" });
    const ctaOpacity = interpolate(frame, [40, 55], [0, 1], { extrapolateRight: "clamp" });

    // パルスアニメーション
    const pulse = interpolate(frame % 30, [0, 15, 30], [1, 1.05, 1]);

    return (
        <AbsoluteFill style={{
            background: `radial-gradient(ellipse at center, #1a1a3a 0%, ${BG_COLOR} 70%)`,
            justifyContent: "center",
            alignItems: "center",
        }}>
            {/* 謎会ロゴ */}
            <div style={{
                position: "absolute",
                top: 480,
                width: "100%",
                textAlign: "center",
                transform: `scale(${logoScale})`,
            }}>
                <div style={{
                    fontSize: 140,
                    fontWeight: 900,
                    color: ACCENT,
                    fontFamily: FONT,
                    letterSpacing: 20,
                    textShadow: `0 0 40px ${ACCENT}44`,
                }}>
                    謎会
                </div>
            </div>

            {/* サブテキスト */}
            <div style={{
                position: "absolute",
                top: 700,
                width: "100%",
                textAlign: "center",
                opacity: textOpacity,
            }}>
                <div style={{
                    fontSize: 34,
                    color: "#aaaacc",
                    fontFamily: FONT,
                    fontWeight: 300,
                    letterSpacing: 3,
                }}>
                    謎は謎のままにしない
                </div>
            </div>

            {/* CTA */}
            <div style={{
                position: "absolute",
                bottom: 450,
                width: "100%",
                textAlign: "center",
                opacity: ctaOpacity,
                transform: `scale(${pulse})`,
            }}>
                <div style={{
                    display: "inline-block",
                    border: `2px solid ${ACCENT}`,
                    borderRadius: 50,
                    padding: "18px 60px",
                    fontSize: 36,
                    color: ACCENT,
                    fontFamily: FONT,
                    fontWeight: 600,
                    letterSpacing: 4,
                }}>
                    noteで続きを読む ↑
                </div>
            </div>
        </AbsoluteFill>
    );
};

// --- メインコンポジション ---
export const StoryVideo: React.FC = () => {
    return (
        <AbsoluteFill style={{ backgroundColor: BG_COLOR }}>
            {/* シーン1: フック 0〜3秒 (0〜90フレーム) */}
            <Sequence from={0} durationInFrames={90}>
                <HookScene />
            </Sequence>

            {/* シーン2: チーム構造 3〜7秒 (90〜210フレーム) */}
            <Sequence from={90} durationInFrames={120}>
                <TeamScene />
            </Sequence>

            {/* シーン3: 予告 7〜12秒 (210〜360フレーム) */}
            <Sequence from={210} durationInFrames={150}>
                <TeaserScene />
            </Sequence>

            {/* シーン4: CTA 12〜15秒 (360〜450フレーム) */}
            <Sequence from={360} durationInFrames={90}>
                <CTAScene />
            </Sequence>
        </AbsoluteFill>
    );
};
