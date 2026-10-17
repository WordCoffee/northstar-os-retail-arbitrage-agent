# Master Plan V2 tooling sweep — GitHub + HuggingFace metadata survey (read-only).
# Writes github_sweep.jsonl (one JSON record per query) + hf_datasets.json.
$ErrorActionPreference = 'Continue'
$root = 'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\master_plan_v2_sweep_20261016'
New-Item -ItemType Directory -Force -Path $root | Out-Null
$gh = Join-Path $root 'github_sweep.jsonl'
$hf = Join-Path $root 'hf_datasets.json'
Remove-Item $gh, $hf -ErrorAction SilentlyContinue

$q = @(
  @('topic:comfyui', 100),
  @('comfyui websocket api client', 30),
  @('comfyui queue progress', 20),
  @('topic:mcp-server', 100),
  @('mcp server browser automation', 40),
  @('chrome devtools protocol mcp', 20),
  @('playwright mcp', 20),
  @('topic:mcp', 100),
  @('topic:whisper', 100),
  @('faster-whisper streaming', 40),
  @('whisper.cpp server', 30),
  @('push-to-talk speech recognition', 30),
  @('realtime audio transcription websocket', 30),
  @('topic:text-to-speech', 100),
  @('kokoro tts', 20),
  @('file watcher hot reload config', 30),
  @('apscheduler background scheduler', 20),
  @('speculative decoding', 40),
  @('dspark', 10),
  @('local llm tool calling agent', 50),
  @('llm tool registry framework', 40),
  @('structured output json schema llm', 30),
  @('google search console api', 30),
  @('keyword rank tracker', 40),
  @('seo analysis open source', 40),
  @('topic:vector-database', 100),
  @('embedded vector search local', 40),
  @('knowledge graph extraction llm', 40),
  @('entity linking knowledge graph', 30),
  @('topic:rag', 100),
  @('semantic search embeddings local', 40),
  @('amazon product data research', 40),
  @('competitor analysis tool', 30),
  @('social media scheduling self-hosted', 40),
  @('cross posting social networks', 30),
  @('machine translation offline', 40),
  @('argos translate', 15),
  @('translation glossary management', 20),
  @('infographic generator', 40),
  @('html to image satori', 20),
  @('image text overlay text rendering', 20),
  @('brand voice analysis', 30),
  @('stylometry text analysis', 20),
  @('a/b testing open source', 40),
  @('experiment platform self hosted', 30),
  @('feature flags self hosted', 30),
  @('llm evaluation harness', 40),
  @('prompt optimization feedback', 30),
  @('amazon reviews dataset', 30),
  @('ecommerce product image dataset', 30),
  @('nutrition facts dataset', 20),
  @('packaging dieline dataset', 20)
)

$i = 0
foreach ($pair in $q) {
  $i++
  $query = $pair[0]; $n = [int]$pair[1]
  $enc = [uri]::EscapeDataString($query)
  $uri = "https://api.github.com/search/repositories?q=$enc&sort=stars&order=desc&per_page=$n"
  $ok = $false
  for ($try = 1; $try -le 2 -and -not $ok; $try++) {
    try {
      $r = Invoke-RestMethod -Headers @{ 'User-Agent' = 'ns-research'; 'Accept' = 'application/vnd.github+json' } -Uri $uri -TimeoutSec 30
      $items = @()
      foreach ($it in $r.items) {
        $lic = $null
        if ($it.license) { $lic = $it.license.spdx_id }
        $items += [pscustomobject]@{
          full_name = $it.full_name; stars = $it.stargazers_count; license = $lic
          pushed = $it.pushed_at; lang = $it.language
          desc = ([string]$it.description); topics = @($it.topics)
        }
      }
      $rec = [pscustomobject]@{ q = $query; total = $r.total_count; items = $items }
      [System.IO.File]::AppendAllText($gh, ($rec | ConvertTo-Json -Depth 6 -Compress) + "`n", [System.Text.Encoding]::UTF8)
      "OK  [$i/$($q.Count)] $query  total=$($r.total_count) fetched=$($items.Count)"
      $ok = $true
    } catch {
      "ERR [$i] $query : $($_.Exception.Message)"
      Start-Sleep -Seconds 20
    }
  }
  Start-Sleep -Seconds 7
}

# HuggingFace datasets (different host; gentle pacing).
$terms = @('amazon product reviews', 'e-commerce product images', 'brand voice', 'copywriting instructions',
  'nutrition facts label', 'social media advertising', 'english glossary translation', 'search terms keyword')
$hfRows = @()
foreach ($t in $terms) {
  try {
    $enc = [uri]::EscapeDataString($t)
    $r = Invoke-RestMethod -Headers @{ 'User-Agent' = 'ns-research' } -Uri "https://huggingface.co/api/datasets?search=$enc&limit=10&sort=downloads&direction=-1" -TimeoutSec 30
    $rows = @($r | ForEach-Object { [pscustomobject]@{ id = $_.id; downloads = $_.downloads; likes = $_.likes; tags = @($_.tags) } })
    $hfRows += [pscustomobject]@{ term = $t; items = $rows }
    "HF  $t -> $($rows.Count) hits"
  } catch { "HF ERR $t : $($_.Exception.Message)" }
  Start-Sleep -Seconds 2
}
[System.IO.File]::WriteAllText($hf, ($hfRows | ConvertTo-Json -Depth 6), [System.Text.Encoding]::UTF8)
"DONE github+HF"
