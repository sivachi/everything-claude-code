
import { DrivePollerService } from '../services/drive-poller';

async function main() {
    console.log('Initializing Drive Poller...');

    try {
        const poller = new DrivePollerService();
        await poller.start();

        // Handle graceful shutdown
        const shutdown = () => {
            console.log('Shutting down...');
            poller.stop();
            process.exit(0);
        };

        process.on('SIGINT', shutdown);
        process.on('SIGTERM', shutdown);

    } catch (error) {
        console.error('Failed to start Drive Poller:', error);
        process.exit(1);
    }
}

main();
