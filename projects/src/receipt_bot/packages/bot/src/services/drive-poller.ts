
import { driveService } from '../lib/drive';
import { analyzeReceiptWithCategory } from '../lib/gemini';
import { getOrCreateUser, uploadReceiptImage, createReceipt, getCategories, Receipt } from '../lib/supabase';
import dotenv from 'dotenv';
import { z } from 'zod';

dotenv.config();

const ConfigSchema = z.object({
    GOOGLE_DRIVE_FOLDER_ID: z.string(),
    GOOGLE_DRIVE_PROCESSED_FOLDER_ID: z.string(),
    DRIVE_TARGET_DISCORD_ID: z.string().default('drive_imported_user'),
    DRIVE_POLL_INTERVAL_MS: z.string().transform(val => parseInt(val, 10)).default('60000'),
});

export class DrivePollerService {
    private config;
    private isPolling = false;

    constructor() {
        try {
            this.config = ConfigSchema.parse(process.env);
            console.log('Drive Poller configuration loaded.');
        } catch (error) {
            console.error('Invalid configuration for Drive Poller:', error);
            throw new Error('Drive Poller configuration failed');
        }
    }

    async start() {
        if (this.isPolling) {
            console.warn('Poller is already running.');
            return;
        }

        this.isPolling = true;
        console.log(`Starting Drive Poller (Interval: ${this.config.DRIVE_POLL_INTERVAL_MS}ms)`);
        console.log(`Monitoring Folder: ${this.config.GOOGLE_DRIVE_FOLDER_ID}`);

        this.pollLoop();
    }

    stop() {
        this.isPolling = false;
        console.log('Stopping Drive Poller...');
    }

    private async pollLoop() {
        while (this.isPolling) {
            try {
                await this.processNewFiles();
            } catch (error) {
                console.error('Error in poll loop:', error);
            }

            // Wait for next interval
            await new Promise(resolve => setTimeout(resolve, this.config.DRIVE_POLL_INTERVAL_MS));
        }
    }

    private async processNewFiles() {
        const files = await driveService.listNewFiles(this.config.GOOGLE_DRIVE_FOLDER_ID);

        if (files.length === 0) {
            return;
        }

        console.log(`Found ${files.length} new files to process.`);

        // Get the target user
        // We use a dummy username for the Drive user
        const user = await getOrCreateUser(
            this.config.DRIVE_TARGET_DISCORD_ID,
            'Google Drive Import'
        );

        const categories = await getCategories();

        for (const file of files) {
            if (!file.id || !file.name) continue;

            try {
                console.log(`Processing file: ${file.name} (${file.id})`);

                // 1. Download content
                const { buffer } = await driveService.downloadFile(file.id);

                // 2. Upload to Supabase Storage
                const uploadResult = await uploadReceiptImage(
                    user.id,
                    buffer,
                    file.name
                );

                // 3. Analyze with Gemini
                const analysis = await analyzeReceiptWithCategory(buffer);

                // 4. Determine Category
                let category = categories.find(c => c.code === analysis.category.code);
                if (!category) {
                    category = categories.find(c => c.code === 'MISC');
                }

                // 5. Save Receipt to Database
                await createReceipt({
                    user_id: user.id,
                    discord_user_id: this.config.DRIVE_TARGET_DISCORD_ID,
                    image_url: uploadResult.url,
                    ocr_raw_text: JSON.stringify(analysis),
                    store_name: analysis.storeName || undefined,
                    amount: analysis.totalAmount || undefined,
                    tax_amount: analysis.taxAmount || undefined,
                    receipt_date: analysis.date || new Date().toISOString().split('T')[0],
                    category_id: category?.id,
                    category_confidence: analysis.category.confidence,
                    is_category_confirmed: false, // Auto-imported, so not confirmed
                    notes: `Imported from Google Drive: ${file.name}`,
                });

                console.log(`Receipt saved for ${file.name}.`);

                // 6. Move file to processed folder
                await driveService.moveFile(
                    file.id,
                    this.config.GOOGLE_DRIVE_FOLDER_ID,
                    this.config.GOOGLE_DRIVE_PROCESSED_FOLDER_ID
                );

            } catch (error) {
                console.error(`Failed to process file ${file.name}:`, error);
                // Continue to next file even if one fails
            }
        }
    }
}
