# Standardized uploaded Tab Musik player

Uploaded Guitar Pro tabs use the shared `tabs/generated-tab-player.js` and `tabs/generated-tab-player.css` assets. The shared player now keeps the global song position when switching instruments, uses a single measure/tick timeline for all tracks, supports Space for play/pause, catches delayed animation frames without drifting one tick at a time, auto-scrolls on measure changes, and uses the same responsive score/player visual structure as the established Tab Musik pages.

The upload generator must continue referencing these shared assets so every newly uploaded GP/GP3/GP4/GP5 file inherits the same behavior automatically.
