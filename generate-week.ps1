param(
    [string]$Week
)

$SheetId = "1Whv4ZlMoBG4TabvzfPl7Eo03i2h0is1LsWd7Lg4nQSI"
$Credentials = ".\service-account.json"

$Args = @(
    "generate.py"
    "--sheet-id"
    $SheetId
    "--credentials"
    $Credentials
)

if ($Week) {
    $Args += "--week"
    $Args += $Week
}

python @Args