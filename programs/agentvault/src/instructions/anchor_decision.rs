use anchor_lang::prelude::*;

use crate::constants::{ARWEAVE_TX_LEN, MAX_DECISION_DATA_LEN, MAX_DECISION_TYPE_LEN};
use crate::errors::AgentVaultError;
use crate::events::DecisionAnchored;
use crate::state::DecisionRecord;

#[derive(Accounts)]
#[instruction(agent_id: Pubkey, decision_type: String, context_hash: [u8;32], arweave_tx: String, decision_data: Vec<u8>, timestamp: i64)]
pub struct AnchorDecision<'info> {
    #[account(mut)]
    pub signer: Signer<'info>,

    #[account(
        init,
        payer = signer,
        space = DecisionRecord::SPACE,
        seeds = [b"decision", agent_id.as_ref(), &timestamp.to_le_bytes()],
        bump,
    )]
    pub decision: Account<'info, DecisionRecord>,

    pub system_program: Program<'info, System>,
}

pub fn handler(
    ctx: Context<AnchorDecision>,
    agent_id: Pubkey,
    decision_type: String,
    context_hash: [u8; 32],
    arweave_tx: String,
    decision_data: Vec<u8>,
    timestamp: i64,
) -> Result<()> {
    require!(
        decision_type.len() <= MAX_DECISION_TYPE_LEN,
        AgentVaultError::DecisionTypeTooLong
    );
    require!(
        decision_data.len() <= MAX_DECISION_DATA_LEN,
        AgentVaultError::DecisionDataTooLarge
    );
    require!(
        arweave_tx.len() == ARWEAVE_TX_LEN,
        AgentVaultError::InvalidArweaveTx
    );

    let clock = Clock::get()?;
    let record = &mut ctx.accounts.decision;
    record.agent_id = agent_id;
    record.decision_type = decision_type.clone();
    record.context_hash = context_hash;
    record.arweave_tx = arweave_tx;
    record.decision_data = decision_data;
    record.timestamp = timestamp;
    record.slot = clock.slot;
    record.bump = ctx.bumps.decision;

    emit!(DecisionAnchored {
        agent_id,
        decision_type,
        context_hash,
        slot: clock.slot,
        timestamp,
    });

    Ok(())
}
