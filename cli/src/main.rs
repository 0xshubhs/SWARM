use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "avlt", version, about = "AgentVault seller CLI")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Capture KV cache from a running vLLM/LMCache instance.
    Capture,
    /// Compress + upload + list a captured cache.
    List,
}

fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Capture => println!("avlt capture: TODO — see docs/00_ARCHITECTURE.md §7 (v0.2)"),
        Commands::List => println!("avlt list: TODO"),
    }
    Ok(())
}
