set repoRoot to POSIX path of (choose folder with prompt "Choose the root folder of the Research Planner repository")
set logPath to repoRoot & "workspace/issue_log.md"
set logFile to POSIX file logPath
set todayDate to do shell script "date +%F"
set timeText to do shell script "date +%H:%M"

try
	display dialog "Which experiment or step did not finish on time?" default answer "" buttons {"Cancel", "Continue"} default button "Continue"
	set experimentName to text returned of result
	if experimentName is "" then error number -128

	display dialog "What blocked it?" default answer "" buttons {"Cancel", "Continue"} default button "Continue"
	set problemText to text returned of result
	if problemText is "" then error number -128

	display dialog "What is the next plan or rescheduled target?" default answer "" buttons {"Cancel", "Save"} default button "Save"
	set nextStepText to text returned of result
	if nextStepText is "" then error number -128

	set recordText to "## " & todayDate & " " & timeText & return & "- Task: " & experimentName & return & "- Blocker: " & problemText & return & "- Next step: " & nextStepText & return & return
	set fileRef to open for access logFile with write permission
	write recordText to fileRef starting at eof
	close access fileRef

	display dialog "Saved to workspace/issue_log.md" buttons {"Open log", "OK"} default button "OK"
	if button returned of result is "Open log" then
		do shell script "open " & quoted form of logPath
	end if
on error errMsg number errNum
	try
		close access logFile
	end try
	if errNum is not -128 then
		display dialog "Issue logger failed:" & return & errMsg buttons {"OK"} default button "OK" with icon stop
	end if
end try
