function Normalize-Text {
  param([string]$s)
  $s = [System.Net.WebUtility]::HtmlDecode($s)
  $s = $s.Replace('&nbsp;', ' ')
  $s = $s -replace '(?is)<script.*?</script>', ' '
  $s = $s -replace '(?is)<style.*?</style>', ' '
  $s = $s -replace '<[^>]+>', ' '
  $s = $s -replace '\s+', ' '
  return $s.Trim()
}

$p1 = 'c:\Users\Edgestation\Documents\VSCode\General Workspace\articles\procurement\kb0011076\kb0011076.html'
$p2 = 'c:\Users\Edgestation\Documents\VSCode\General Workspace\articles\procurement\kb0011076\kb0011076-new.html'

$oldText = Normalize-Text (Get-Content $p1 -Raw)
$newTextRaw = Get-Content $p2 -Raw
$bodyMatch = [regex]::Match($newTextRaw, '(?is)<div\s+class="smith-body-wrapper"[^>]*>(.*?)</div>\s*$')
if ($bodyMatch.Success) {
  $newBody = $bodyMatch.Groups[1].Value
} else {
  $newBody = $newTextRaw
}
$newText = Normalize-Text $newBody

"OLD_LEN: $($oldText.Length)"
"NEW_LEN: $($newText.Length)"
"EQUAL: $($oldText -ceq $newText)"
if ($oldText -cne $newText) {
  $a = @($oldText.Split(' '))
  $b = @($newText.Split(' '))
  Compare-Object -ReferenceObject $a -DifferenceObject $b | Select-Object -First 25 -ExpandProperty InputObject
}
