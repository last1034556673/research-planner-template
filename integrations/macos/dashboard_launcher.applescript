set repoRoot to POSIX path of (choose folder with prompt "Choose the root folder of the Research Planner repository")
set plannerCommand to "cd " & quoted form of repoRoot & " && python3 -m planner.cli"

try
	set actionChoice to button returned of (display dialog "Research Planner template" & return & return & "Choose whether to refresh the dashboard only or prepare today's report first." buttons {"Cancel", "Refresh dashboard", "Prepare report + refresh"} default button "Prepare report + refresh")
	if actionChoice is "Refresh dashboard" then
		do shell script plannerCommand & " refresh"
	else if actionChoice is "Prepare report + refresh" then
		set reportPath to do shell script plannerCommand & " prepare-report"
		do shell script "open " & quoted form of reportPath
		display dialog "The daily report was created at:" & return & reportPath & return & return & "Fill it in, save it, then continue." buttons {"Cancel", "Continue"} default button "Continue"
		do shell script plannerCommand & " ingest-report --input " & quoted form of reportPath
	end if
on error errMsg number errNum
	if errNum is not -128 then
		display dialog "Research Planner launcher failed:" & return & errMsg buttons {"OK"} default button "OK" with icon stop
	end if
end try
