// `pub use *::*` is required so the #[program] macro can resolve the
// auto-generated `__client_accounts_*` modules at the crate root.
// We hide each instruction's `handler` from re-export to avoid name clashes.

pub mod initialize_platform;
pub mod list_memory;
pub mod buy_memory;
pub mod buy_sandbox_access;
pub mod delist_memory;
pub mod update_listing_price;
pub mod anchor_decision;

#[allow(ambiguous_glob_reexports)]
mod _exports {
    pub use super::initialize_platform::*;
    pub use super::list_memory::*;
    pub use super::buy_memory::*;
    pub use super::buy_sandbox_access::*;
    pub use super::delist_memory::*;
    pub use super::update_listing_price::*;
    pub use super::anchor_decision::*;
}

pub use _exports::*;
