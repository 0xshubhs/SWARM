//! AgentVault CLI (`avlt`)
//!
//! v0.1 ships with read-only and upload subcommands. Buy / audit-anchor
//! operations need a Solana wallet integration that's tracked for v0.2.
use anyhow::{anyhow, Context, Result};
use clap::{Parser, Subcommand};
use indicatif::{ProgressBar, ProgressStyle};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::path::PathBuf;
use std::time::Duration;
use tokio::fs;

#[derive(Parser, Debug)]
#[command(
    name = "avlt",
    version,
    about = "AgentVault CLI — capture, list, buy, and audit AI agent memory",
    propagate_version = true
)]
struct Cli {
    /// Backend base URL (overrides env AGENTVAULT_BACKEND_URL).
    #[arg(long, env = "AGENTVAULT_BACKEND_URL", default_value = "http://localhost:8000")]
    backend: String,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Capture KV cache from a running vLLM/LMCache instance into a `.avlt` file.
    Capture {
        /// Where to write the captured blob.
        #[arg(long, default_value = "memory.avlt")]
        out: PathBuf,
        /// LMCache remote endpoint to pull from.
        #[arg(long, env = "LMCACHE_REMOTE_URL")]
        lmcache: Option<String>,
    },

    /// Compress + upload + list a captured cache. Calls /v1/upload/init then
    /// /v1/upload/blob.
    List {
        /// Path to the captured `.avlt` file.
        path: PathBuf,
        #[arg(long)]
        seller: String,
        #[arg(long)]
        title: String,
        #[arg(long, value_delimiter = ',', num_args = 1..)]
        tags: Vec<String>,
        #[arg(long, default_value_t = 25.0)]
        price_usdc: f64,
        #[arg(long, default_value_t = 0.05)]
        sandbox_price_usdc: f64,
    },

    /// Read a listing's on-chain metadata via the backend mirror.
    Show {
        /// Listing PDA (base58).
        id: String,
    },

    /// Hash a local file and ask the backend whether it's anchored.
    Verify { path: PathBuf },

    /// Anchor a decision context. v0.2 — requires wallet integration.
    Audit {
        #[arg(long)]
        agent: String,
        #[arg(long)]
        decision_type: String,
        #[arg(long)]
        context: PathBuf,
    },
}

#[derive(Deserialize, Debug)]
#[serde(rename_all = "snake_case")]
struct UploadInitResponse {
    upload_id: String,
    fee_breakdown: FeeBreakdown,
    fee_payment_address: String,
    #[allow(dead_code)]
    ws_token: String,
    ws_channel: String,
}

#[derive(Deserialize, Debug)]
#[serde(rename_all = "snake_case")]
struct FeeBreakdown {
    base_usdc: u64,
    compute_usdc: u64,
    storage_usdc: u64,
    total_usdc: u64,
}

#[tokio::main]
async fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Capture { out, lmcache } => capture(&out, lmcache.as_deref()).await,
        Commands::List {
            path,
            seller,
            title,
            tags,
            price_usdc,
            sandbox_price_usdc,
        } => list_memory(
            &cli.backend,
            &path,
            &seller,
            &title,
            &tags,
            price_usdc,
            sandbox_price_usdc,
        )
        .await,
        Commands::Show { id } => show_listing(&cli.backend, &id).await,
        Commands::Verify { path } => verify_blob(&cli.backend, &path).await,
        Commands::Audit { .. } => {
            println!("avlt audit: requires wallet integration (v0.2). See docs/01_SOLANA_PROGRAM.md §3.7");
            Ok(())
        }
    }
}

async fn capture(out: &PathBuf, lmcache: Option<&str>) -> Result<()> {
    if let Some(url) = lmcache {
        println!("Capturing from {} → {}", url, out.display());
        let r = reqwest::get(url).await?.error_for_status()?;
        let bytes = r.bytes().await?;
        fs::write(out, &bytes).await?;
        println!("✓ wrote {} bytes", bytes.len());
    } else {
        println!(
            "v0.1 capture is a stub. Set --lmcache <URL> or use the runbook scripts to dump KV cache from your local vLLM instance."
        );
    }
    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn list_memory(
    backend: &str,
    path: &PathBuf,
    seller: &str,
    title: &str,
    tags: &[String],
    price_usdc: f64,
    sandbox_price_usdc: f64,
) -> Result<()> {
    let bytes = fs::read(path).await.with_context(|| format!("reading {}", path.display()))?;
    let size = bytes.len();
    println!("File: {} ({} bytes)", path.display(), size);

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(120))
        .build()?;
    let init: UploadInitResponse = client
        .post(format!("{backend}/v1/upload/init"))
        .json(&serde_json::json!({
            "seller_pubkey": seller,
            "expected_size_bytes": size,
        }))
        .send()
        .await?
        .error_for_status()?
        .json()
        .await?;

    println!("upload_id: {}", init.upload_id);
    println!(
        "fee: ${:.2} USDC (base ${:.2} + compute ${:.2} + storage ${:.2})",
        init.fee_breakdown.total_usdc as f64 / 1e6,
        init.fee_breakdown.base_usdc as f64 / 1e6,
        init.fee_breakdown.compute_usdc as f64 / 1e6,
        init.fee_breakdown.storage_usdc as f64 / 1e6,
    );
    println!("payment to: {}", init.fee_payment_address);
    println!("ws channel: {}{}", backend.trim_end_matches('/'), init.ws_channel);

    let pb = ProgressBar::new(size as u64);
    pb.set_style(
        ProgressStyle::with_template(
            "{spinner:.cyan} [{elapsed_precise}] [{bar:30.green/blue}] {bytes}/{total_bytes}",
        )
        .unwrap()
        .progress_chars("=> "),
    );
    pb.set_position(size as u64);

    let local_hash = {
        let mut h = Sha256::new();
        h.update(&bytes);
        hex::encode(h.finalize())
    };
    println!("local sha256: {local_hash}");

    let part = reqwest::multipart::Part::bytes(bytes).file_name(
        path.file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_else(|| "memory.avlt".into()),
    );
    let form = reqwest::multipart::Form::new().part("blob", part);
    let r = client
        .post(format!(
            "{}/v1/upload/blob/{}",
            backend, init.upload_id
        ))
        .multipart(form)
        .send()
        .await?;

    if !r.status().is_success() {
        return Err(anyhow!(
            "upload failed: {} {}",
            r.status(),
            r.text().await.unwrap_or_default()
        ));
    }
    pb.finish_with_message("uploaded");

    println!(
        "\nNext: subscribe to {ws} to watch compress/arweave progress, then sign the listMemory tx.\n  title  = {title:?}\n  tags   = {tags:?}\n  prices = ${price_usdc} (buy) / ${sandbox_price_usdc} (sandbox)",
        ws = init.ws_channel
    );
    Ok(())
}

async fn show_listing(backend: &str, id: &str) -> Result<()> {
    let r = reqwest::get(format!("{backend}/v1/listings/{id}"))
        .await?
        .error_for_status()?;
    let v: serde_json::Value = r.json().await?;
    println!("{}", serde_json::to_string_pretty(&v)?);
    Ok(())
}

async fn verify_blob(backend: &str, path: &PathBuf) -> Result<()> {
    let bytes = fs::read(path).await?;
    let mut h = Sha256::new();
    h.update(&bytes);
    let hash = hex::encode(h.finalize());
    println!("sha256: {hash}");

    let r = reqwest::get(format!("{backend}/v1/verify/{hash}"))
        .await?
        .error_for_status()?;
    let v: serde_json::Value = r.json().await?;
    println!("{}", serde_json::to_string_pretty(&v)?);
    Ok(())
}
