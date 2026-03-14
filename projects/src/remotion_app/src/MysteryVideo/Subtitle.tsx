import React from 'react';
import { interpolate, useCurrentFrame } from 'remotion';

export const Subtitle: React.FC<{ text: string }> = ({ text }) => {
    const frame = useCurrentFrame();
    const opacity = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: 'clamp' });

    return (
        <div style={{
            position: 'absolute',
            bottom: 80,
            width: '100%',
            textAlign: 'center',
            fontSize: 50,
            color: 'white',
            fontFamily: 'sans-serif',
            textShadow: '2px 2px 4px black, 0 0 10px black',
            padding: '0 40px',
            opacity,
        }}>
            {text}
        </div>
    );
};
