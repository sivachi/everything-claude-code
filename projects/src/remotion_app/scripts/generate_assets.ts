
import dotenv from "dotenv";
import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";
import Replicate from "replicate";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Load environment variables
dotenv.config();

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PUBLIC_DIR = path.resolve(__dirname, "../public/mystery-assets");

// Ensure public directory exists
if (!fs.existsSync(PUBLIC_DIR)) {
    fs.mkdirSync(PUBLIC_DIR, { recursive: true });
}

// ------------------------------------------------------------------
// CONFIGURATION
// ------------------------------------------------------------------

const ELEVENLABS_API_KEY = process.env.ELEVENLABS_API_KEY;
const REPLICATE_API_TOKEN = process.env.REPLICATE_API_TOKEN;

if (!ELEVENLABS_API_KEY || !REPLICATE_API_TOKEN) {
    console.error("Missing API keys in .env file");
    process.exit(1);
}

const elevenlabs = new ElevenLabsClient({ apiKey: ELEVENLABS_API_KEY });
const replicate = new Replicate({ auth: REPLICATE_API_TOKEN });

// ------------------------------------------------------------------
// DATA (SCRIPT)
// ------------------------------------------------------------------

const SCENES = [
    {
        id: "scene1",
        text: "ようこそ、こよいの「なぞかい」へ。私たちは、歴史の教科書が決して語らない「すきま」にある真実を探求する集まりです。",
        voiceIdx: 0, // Narrator
        imagePrompt: "Dark ocean at night, subtle waves, mysterious atmosphere, ancient feeling, cinematic lighting, photorealistic, 8k",
    },
    {
        id: "scene2",
        text: "皆さん、「アトランティス」という言葉を聞いて、何を思い浮かべますか？海に沈んだ幻の都市？プラトンが描いたおとぎ話？それとも、ハリウッド映画のファンタジーでしょうか。",
        voiceIdx: 0,
        imagePrompt: "Ancient burning map transforming into modern world map, magical transition effect, cinematic lighting, highly detailed",
    },
    {
        id: "scene3",
        text: "もし、アトランティスが「海に沈んでいない」としたら？もし、彼らが持っていたテクノロジーが、機械ではなく「精神（スピリチュアル）」によるものだったとしたら？",
        voiceIdx: 0, // User changed to 0 (Narrator)
        imagePrompt: "Glowing ancient Atlantis symbol appearing on dark background, spiritual energy, mysticism, detailed texture, cinematic",
    },
    {
        id: "scene4",
        text: "今日は、いちまんにせんねんまえの記憶を呼び覚ます旅に出かけましょう。準備はいいですか？ 深呼吸をしてください。常識という名の重りを、今ここで捨ててしまいましょう。",
        voiceIdx: 0,
        imagePrompt: "Underwater ancient ruins, ethereal light beams from above, mystical atmosphere, submerged city, hyperrealistic, 8k",
    }
];

// eleven_turbo_v2_5: cheaper & faster than multilingual_v2, supports Japanese
const MODEL_ID = "eleven_turbo_v2_5";

// ------------------------------------------------------------------
// FUNCTIONS
// ------------------------------------------------------------------

async function generateAudio(text: string, voiceId: string, outputPath: string) {
    if (fs.existsSync(outputPath) && fs.statSync(outputPath).size > 0) {
        console.log(`Audio already exists: ${outputPath}`);
        return;
    }

    console.log(`Generating audio for: "${text.substring(0, 20)}..."`);

    try {
        const audioStream = await elevenlabs.textToSpeech.convert(voiceId, {
            text: text,
            modelId: MODEL_ID,
            outputFormat: "mp3_44100_128",
        });

        // The new SDK returns a ReadableStream<Uint8Array>
        const reader = audioStream.getReader();
        const chunks: Uint8Array[] = [];
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            if (value) chunks.push(value);
        }
        const buffer = Buffer.concat(chunks);
        fs.writeFileSync(outputPath, buffer);
        console.log(`Audio generated: ${outputPath}`);

    } catch (error) {
        console.error("Error generating audio:", error);
    }
}

async function generateImage(prompt: string, outputPath: string) {
    if (fs.existsSync(outputPath) && fs.statSync(outputPath).size > 0) {
        console.log(`Image already exists: ${outputPath}`);
        return;
    }

    console.log(`Generating image for prompt: "${prompt}"`);

    try {
        // FLUX Schnell: free tier on Replicate, fast, high quality, supports 16:9
        const output = await replicate.run(
            "black-forest-labs/flux-schnell",
            {
                input: {
                    prompt: prompt + ", cinematic, highly detailed, photorealistic",
                    aspect_ratio: "16:9",
                    num_outputs: 1,
                    output_format: "jpg",
                    output_quality: 90,
                }
            }
        );

        if (Array.isArray(output) && output.length > 0) {
            const imageUrl = output[0];
            const response = await fetch(imageUrl);
            const buffer = await response.arrayBuffer();
            fs.writeFileSync(outputPath, Buffer.from(buffer));
            console.log(`Saved image to ${outputPath}`);
        } else {
            console.error("Replicate output format unexpected:", output);
        }
    } catch (error: any) {
        if (
            error.status === 402 ||
            error.status === 429 ||
            (error.message && (error.message.includes("402") || error.message.includes("429")))
        ) {
            console.error(`⚠️ Replicate Error (${error.status || "Unknown"}): Skipping image generation.`);
            // Create a placeholder image (black background) so the video can still build
            // We can't easily create a binary jpg here without a library, but we can touch the file 
            // or copy the existing sample image if available?
            // Let's just create an empty file for now and handle it in Remotion (or the user will see black)
            // Better: Copy the sample image `S__2768900.jpg` if it exists as a fallback?
            const sampleImg = path.join(__dirname, "../public/S__2768900.jpg");
            if (fs.existsSync(sampleImg)) {
                fs.copyFileSync(sampleImg, outputPath);
                console.log(`Used fallback image for ${outputPath}`);
            }
        } else {
            console.error("Error generating image:", error);
        }
    }
}

// ------------------------------------------------------------------
// MAIN EXECUTION
// ------------------------------------------------------------------

async function main() {
    console.log("Starting asset generation...");

    // Resolve Voice IDs
    let narratorVoiceId = "E7YvDy47DfETMlqyHdLS"; // Clutch Voice ID from User
    // const clutchId = await getVoiceIdByName("Clutch"); // No longer needed
    // if (clutchId) {
    //     console.log(`Found voice 'Clutch' with ID: ${clutchId}`);
    //     narratorVoiceId = clutchId;
    // } else {
    //     console.log("Voice 'Clutch' not found, using default 'Adam'.");
    // }

    const resolvedVoiceIds = [narratorVoiceId, "ErXwobaYiN019PkySvjV"];

    for (const scene of SCENES) {
        // Audio
        const audioPath = path.join(PUBLIC_DIR, `${scene.id}.mp3`);
        await generateAudio(scene.text, resolvedVoiceIds[scene.voiceIdx], audioPath);

        // Image
        const imagePath = path.join(PUBLIC_DIR, `${scene.id}.jpg`);
        await generateImage(scene.imagePrompt, imagePath);
    }

    console.log("Asset generation complete!");
}

main().catch(console.error);
