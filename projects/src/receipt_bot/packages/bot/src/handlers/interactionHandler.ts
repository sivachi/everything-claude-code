import { Interaction } from 'discord.js';
import { commands } from '../commands';

export async function handleInteraction(interaction: Interaction) {
  if (!interaction.isChatInputCommand()) return;

  const { commandName } = interaction;

  if (commandName === 'receipt') {
    const subcommandGroup = interaction.options.getSubcommandGroup(false);
    const subcommand = interaction.options.getSubcommand();

    try {
      if (subcommandGroup === 'category') {
        // Handle category subcommand group
        const handler = commands.receipt.category[subcommand as keyof typeof commands.receipt.category];
        if (handler) {
          await handler(interaction);
        } else {
          await interaction.reply({
            content: 'このコマンドはまだ実装されていません。',
            ephemeral: true,
          });
        }
      } else if (subcommandGroup === 'notify') {
        // Handle notify subcommand group
        await commands.receipt.notify(interaction);
      } else {
        // Handle direct subcommands
        const handler = commands.receipt[subcommand as keyof typeof commands.receipt];
        if (handler && typeof handler === 'function') {
          await handler(interaction);
        } else {
          await interaction.reply({
            content: 'このコマンドはまだ実装されていません。',
            ephemeral: true,
          });
        }
      }
    } catch (error) {
      console.error('Error handling command:', error);
      
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      
      if (interaction.replied || interaction.deferred) {
        await interaction.followUp({
          content: `エラーが発生しました: ${errorMessage}`,
          ephemeral: true,
        });
      } else {
        await interaction.reply({
          content: `エラーが発生しました: ${errorMessage}`,
          ephemeral: true,
        });
      }
    }
  } else if (commandName === 'tag') {
    const subcommand = interaction.options.getSubcommand();

    try {
      const handler = commands.tag[subcommand as keyof typeof commands.tag];
      if (handler && typeof handler === 'function') {
        await handler(interaction);
      } else {
        await interaction.reply({
          content: 'このコマンドはまだ実装されていません。',
          ephemeral: true,
        });
      }
    } catch (error) {
      console.error('Error handling tag command:', error);
      
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      
      if (interaction.replied || interaction.deferred) {
        await interaction.followUp({
          content: `エラーが発生しました: ${errorMessage}`,
          ephemeral: true,
        });
      } else {
        await interaction.reply({
          content: `エラーが発生しました: ${errorMessage}`,
          ephemeral: true,
        });
      }
    }
  }
}