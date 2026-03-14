
import { google } from 'googleapis';
import { Readable } from 'stream';

export class GoogleDriveService {
    private drive;

    constructor() {
        // Look for credentials from environment variable or default path
        if (!process.env.GOOGLE_APPLICATION_CREDENTIALS) {
            console.warn('Warning: GOOGLE_APPLICATION_CREDENTIALS not set. Drive service may fail.');
        }

        const auth = new google.auth.GoogleAuth({
            scopes: ['https://www.googleapis.com/auth/drive'],
        });

        this.drive = google.drive({ version: 'v3', auth });
    }

    /**
     * List files in a specific folder that are images
     */
    async listNewFiles(folderId: string) {
        try {
            const response = await this.drive.files.list({
                q: `'${folderId}' in parents and mimeType contains 'image/' and trashed = false`,
                fields: 'files(id, name, mimeType, webContentLink)',
                orderBy: 'createdTime desc',
                pageSize: 10,
            });

            return response.data.files || [];
        } catch (error) {
            console.error('Error listing files from Drive:', error);
            throw error;
        }
    }

    /**
     * Download a file's content as a Buffer
     */
    async downloadFile(fileId: string): Promise<{ buffer: Buffer; mimeType: string }> {
        try {
            // First get metadata to know the mimeType
            const meta = await this.drive.files.get({
                fileId,
                fields: 'mimeType, name'
            });

            const response = await this.drive.files.get(
                { fileId, alt: 'media' },
                { responseType: 'arraybuffer' }
            );

            return {
                buffer: Buffer.from(response.data as ArrayBuffer),
                mimeType: meta.data.mimeType || 'application/octet-stream'
            };
        } catch (error) {
            console.error(`Error downloading file ${fileId}:`, error);
            throw error;
        }
    }

    /**
     * Move a file to a different folder (by adding new parent and removing old one)
     */
    async moveFile(fileId: string, currentFolderId: string, targetFolderId: string) {
        try {
            // Retrieve the existing parents to remove
            const file = await this.drive.files.get({
                fileId,
                fields: 'parents',
            });

            const previousParents = file.data.parents?.join(',') || '';

            await this.drive.files.update({
                fileId,
                addParents: targetFolderId,
                removeParents: previousParents,
                fields: 'id, parents',
            });

            console.log(`Moved file ${fileId} to folder ${targetFolderId}`);
        } catch (error) {
            console.error(`Error moving file ${fileId}:`, error);
            throw error;
        }
    }
}

export const driveService = new GoogleDriveService();
