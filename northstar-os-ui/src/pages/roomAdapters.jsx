// ROUTE ADAPTERS for room pages written against the pre-router shell.
//
// The legacy rooms (Hub, Ledger, Prospector, …) and the foundation pages were
// built when App.jsx rendered them by hand and passed `toast` — and, for Hub,
// `navigate` — as props. The router mounts a page with no props, so importing
// one directly would leave `toast` undefined and throw on the first click.
// Instead of editing eleven pages to call the hooks themselves, the router
// mounts these adapters, which supply the same contract from context.
//
// This is the single place the prop-era contract is translated; a new room
// should take its dependencies from hooks and be routed directly.

import { useNavigate } from 'react-router-dom'
import { useToast } from '../components/ToastContext.jsx'

import Hub from './Hub.jsx'
import Ledger from './Ledger.jsx'
import Prospector from './Prospector.jsx'
import LegacyGoldenGoose from './GoldenGoose.jsx'
import OfferChisel from './OfferChisel.jsx'
import TownCrier from './TownCrier.jsx'
import Auctioneer from './Auctioneer.jsx'
import TheWatch from './TheWatch.jsx'
import RankLedger from './RankLedger.jsx'
import RivalBoard from './RivalBoard.jsx'

import FoundationStatus from '../foundation/pages/FoundationStatus.jsx'
import Jobs from '../foundation/pages/Jobs.jsx'
import Keywords from '../foundation/pages/Keywords.jsx'
import BetaSignup from '../foundation/pages/BetaSignup.jsx'

function room(Component) {
  function RoomRoute() {
    const { toast } = useToast()
    const navigate = useNavigate()
    return <Component toast={toast} navigate={navigate} />
  }
  RoomRoute.displayName = `RoomRoute(${Component.displayName || Component.name || 'Room'})`
  return RoomRoute
}

export const HubRoom = room(Hub)
export const LedgerRoom = room(Ledger)
export const ProspectorRoom = room(Prospector)
export const LegacyGoldenGooseRoom = room(LegacyGoldenGoose)
export const OfferChiselRoom = room(OfferChisel)
export const TownCrierRoom = room(TownCrier)
export const AuctioneerRoom = room(Auctioneer)
export const TheWatchRoom = room(TheWatch)
export const RankLedgerRoom = room(RankLedger)
export const RivalBoardRoom = room(RivalBoard)

export const FoundationStatusRoom = room(FoundationStatus)
export const JobsRoom = room(Jobs)
export const KeywordsRoom = room(Keywords)
export const BetaSignupRoom = room(BetaSignup)
