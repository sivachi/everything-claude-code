import { Client, GatewayIntentBits, REST, Routes } from 'discord.js';
import dotenv from 'dotenv';
import { registerCommands } from './commands';
import { handleInteraction } from './handlers/interactionHandler';
import { NotificationScheduler } from './lib/scheduler';

dotenv.config();

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
  ],
});

// スケジューラーのインスタンス
let scheduler: NotificationScheduler;

client.once('ready', async () => {
  console.log(`Logged in as ${client.user?.tag}!`);
  
  // スケジューラーを開始
  scheduler = new NotificationScheduler(client);
  scheduler.start();
  
  // Register slash commands
  const rest = new REST({ version: '10' }).setToken(process.env.DISCORD_BOT_TOKEN!);
  
  try {
    console.log('Started refreshing application (/) commands.');
    
    await rest.put(
      Routes.applicationCommands(process.env.DISCORD_CLIENT_ID!),
      { body: registerCommands() },
    );
    
    console.log('Successfully reloaded application (/) commands.');
  } catch (error) {
    console.error('Error registering commands:', error);
  }
});

// グレースフルシャットダウン
process.on('SIGINT', () => {
  console.log('Shutting down...');
  if (scheduler) {
    scheduler.stop();
  }
  client.destroy();
  process.exit(0);
});

client.on('interactionCreate', handleInteraction);

client.login(process.env.DISCORD_BOT_TOKEN);