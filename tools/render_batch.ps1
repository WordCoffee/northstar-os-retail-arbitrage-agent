# Batch five 5-second Wan 2.2 TI2V-5B clips from one product still.
# Sequential on purpose: the card has one tenant at a time. Writes one JSON line
# per clip to reports/video_scan/batch/summary.jsonl and logs to batch/log.txt.
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

$outDir = Join-Path $repo 'reports\video_scan\batch'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$log = Join-Path $outDir 'log.txt'
$summary = Join-Path $outDir 'summary.jsonl'
$image = Join-Path $repo 'Northstar_backend\data\studio_generated\mogra_forest_dusk_composed.png'

$neg = 'static, frozen, jitter, flicker, warping, distorted label text, morphing letters, ' +
       'melting packaging, product moving, camera shake, low quality, watermark, extra objects, people'

$jobs = @(
  @{ name = 'clip_01_dolly'; seed = 42;   prompt = 'Slow cinematic dolly-in toward two matte stand-up pouches of Mogra Organics mushroom powder, forest green and black, on a warm wooden table inside a sunlit greenhouse. Soft afternoon light drifting through the glass, leaves swaying slightly out of focus, fine dust motes in the sunbeams. The pouches stay perfectly still and the label text stays sharp and unchanged. Premium organic product commercial, shallow depth of field.' },
  @{ name = 'clip_02_orbit'; seed = 137;  prompt = 'Gentle arc shot orbiting left to right around two matte stand-up pouches of Mogra Organics mushroom powder, forest green and black, on a wooden table in a sunlit greenhouse. Background foliage drifts softly, warm light glints across the matte packaging. The pouches stay perfectly still and the label text stays sharp and unchanged. Premium organic product commercial.' },
  @{ name = 'clip_03_rackfocus'; seed = 2024; prompt = 'Rack focus from the sunlit greenhouse foliage in the background to two matte stand-up pouches of Mogra Organics mushroom powder, forest green and black, in the foreground on a wooden table. Soft bokeh, warm afternoon light, tiny dust motes. The pouches stay perfectly still and the label text stays sharp and unchanged. Premium organic product commercial.' },
  @{ name = 'clip_04_light'; seed = 777;  prompt = 'Warm sunbeams sweep slowly across a wooden table where two matte stand-up pouches of Mogra Organics mushroom powder, forest green and black, stand side by side in a greenhouse. Dust motes float in the light, soft shadows drift over the matte packaging. The pouches stay perfectly still and the label text stays sharp and unchanged. Premium organic product commercial.' },
  @{ name = 'clip_05_pushin'; seed = 5150; prompt = 'Slight low-angle push-in toward two matte stand-up pouches of Mogra Organics mushroom powder, forest green and black, on a wooden table in a sunlit greenhouse, soft breeze moving the leaves behind them, gentle parallax. The pouches stay perfectly still and the label text stays sharp and unchanged. Premium organic product commercial, shallow depth of field.' }
)

foreach ($j in $jobs) {
    $out = Join-Path $outDir ($j.name + '.webm')
    "==== $($j.name) seed=$($j.seed) $(Get-Date -Format 'HH:mm:ss') ====" | Out-File -FilePath $log -Append -Encoding utf8
    python tools\render_wan_clip.py `
        --image $image --prompt $j.prompt --negative $neg `
        --out $out --length 121 --width 960 --height 960 --steps 30 --seed $j.seed `
        --summary $summary *>> $log
}

# Delivery copies: H.264 MP4 next to every webm.
Get-ChildItem $outDir -Filter '*.webm' | ForEach-Object {
    $mp4 = [IO.Path]::ChangeExtension($_.FullName, '.mp4')
    & ffmpeg -v error -y -i $_.FullName -c:v libx264 -pix_fmt yuv420p -crf 20 -movflags +faststart $mp4 *>> $log
}

"DONE $(Get-Date -Format 'HH:mm:ss')" | Out-File -FilePath $log -Append -Encoding utf8
