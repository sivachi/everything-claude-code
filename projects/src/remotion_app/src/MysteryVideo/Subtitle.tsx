import React from 'react';
import { interpolate, useCurrentFrame, useVideoConfig } from 'remotion';

export const Subtitle: React.FC<{ text: string }> = ({ text }) => {
    const frame = useCurrentFrame();
    const { durationInFrames } = useVideoConfig();

    // Fade in over 1 second
    const fadeIn = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: 'clamp' });
    // Fade out over last 1 second
    const fadeOut = interpolate(
        frame,
        [durationInFrames - 30, durationInFrames],
        [1, 0],
        { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
    );
    const opacity = fadeIn * fadeOut;

    return (
        <div style={{
            position: 'absolute',
            bottom: 60,
            left: 0,
            width: '100%',
            display: 'flex',
            justifyContent: 'center',
            padding: '0 60px',
            opacity,
        }}>
            <div style={{
                backgroundColor: 'rgba(0, 0, 0, 0.6)',
                borderRadius: 8,
                padding: '16px 32px',
                fontSize: 42,
                color: 'white',
                fontFamily: "'Noto Sans JP', 'Hiragino Sans', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', system-ui, sans-serif",
                textAlign: 'center',
                lineHeight: 1.6,
                wordBreak: 'keep-all',
                overflowWrap: 'break-word',
                textShadow: '1px 1px 3px rgba(0,0,0,0.8)',
                maxWidth: '85%',
            }}>
                {text}
            </div>
        </div>
    );
};
