import argparse
import subprocess
import os
import sys
import boto3

def send_sns_notification(sns_arn, iac_tool, iac_dir, details):
    """Sends a notification to AWS SNS."""
    if not sns_arn:
        print("WARNING: Drift detected, but no SNS ARN provided. Skipping notification.")
        return
        
    try:
        print(f"Sending notification to SNS topic: {sns_arn}")
        client = boto3.client('sns', region_name=sns_arn.split(':')[3])
        message = (
            f"⚠️ IaC Drift Detected!\n\n"
            f"Tool: {iac_tool.upper()}\n"
            f"Directory: {iac_dir}\n\n"
            f"Details:\n{details}\n"
        )
        client.publish(
            TopicArn=sns_arn,
            Subject=f"IaC Drift Alert - {iac_tool.upper()}",
            Message=message
        )
        print("Notification sent successfully.")
    except Exception as e:
        print(f"ERROR: Failed to send SNS notification: {e}")

def detect_drift(iac_tool, iac_dir):
    """Executes the specific IaC drift detection command."""
    print(f"Starting drift detection for {iac_tool} in {iac_dir}")
    
    if not os.path.isdir(iac_dir):
        print(f"ERROR: Directory {iac_dir} does not exist.")
        sys.exit(1)

    drift_detected = False
    output = ""
    command = []

    try:
        if iac_tool == "terraform":
            # Terraform init first
            subprocess.run(["terraform", "init", "-no-color"], cwd=iac_dir, check=True, capture_output=True)
            # Detailed exitcode: 0 = empty diff, 1 = error, 2 = diff present
            command = ["terraform", "plan", "-detailed-exitcode", "-no-color"]
            result = subprocess.run(command, cwd=iac_dir, capture_output=True, text=True)
            
            if result.returncode == 2:
                drift_detected = True
                output = result.stdout
            elif result.returncode != 0:
                print(f"ERROR: Terraform plan failed: {result.stderr}")
                sys.exit(1)
                
        elif iac_tool == "opentofu":
            # Tofu init first
            subprocess.run(["tofu", "init", "-no-color"], cwd=iac_dir, check=True, capture_output=True)
            command = ["tofu", "plan", "-detailed-exitcode", "-no-color"]
            result = subprocess.run(command, cwd=iac_dir, capture_output=True, text=True)
            
            if result.returncode == 2:
                drift_detected = True
                output = result.stdout
            elif result.returncode != 0:
                print(f"ERROR: OpenTofu plan failed: {result.stderr}")
                sys.exit(1)
                
        elif iac_tool == "ansible":
            # Ansible check mode
            # Assuming playbook.yml or site.yml. We need to find the main playbook.
            playbook = "playbook.yml"
            if not os.path.exists(os.path.join(iac_dir, playbook)):
                playbook = "site.yml"
            
            if not os.path.exists(os.path.join(iac_dir, playbook)):
                print(f"ERROR: Could not find playbook.yml or site.yml in {iac_dir}")
                sys.exit(1)
                
            command = ["ansible-playbook", playbook, "--check"]
            result = subprocess.run(command, cwd=iac_dir, capture_output=True, text=True)
            
            # Ansible doesn't have a specific exit code for "changes required" in standard run
            # but we can look at the output for "changed="
            if result.returncode != 0:
                print(f"ERROR/DRIFT: Ansible run failed or found issues: {result.stderr}")
                drift_detected = True
                output = result.stdout + "\n" + result.stderr
            else:
                if "changed=0" not in result.stdout and "changed=" in result.stdout:
                    # Parse better if needed, for now any 'changed' > 0 means drift
                    # Usually "changed=1" etc at the PLAY RECAP
                    recap = result.stdout.split("PLAY RECAP")[-1]
                    if "changed=0" not in recap:
                        drift_detected = True
                        output = result.stdout
                        
        elif iac_tool == "pulumi":
            # Pulumi preview
            command = ["pulumi", "preview", "--expect-no-changes"]
            result = subprocess.run(command, cwd=iac_dir, capture_output=True, text=True)
            
            if result.returncode != 0:
                drift_detected = True
                output = result.stdout + "\n" + result.stderr
                
        else:
            print(f"ERROR: Unsupported IaC tool: {iac_tool}")
            sys.exit(1)

    except FileNotFoundError as e:
        print(f"ERROR: Tool binary not found: {e.filename}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: An unexpected error occurred: {e}")
        sys.exit(1)

    return drift_detected, output

def main():
    parser = argparse.ArgumentParser(description="IaC Drift Detection Script")
    parser.add_argument("--iac-dir", required=True, help="Directory containing the IaC source code")
    parser.add_argument("--iac-tool", required=True, help="The IaC tool to use (terraform, opentofu, ansible, pulumi)")
    parser.add_argument("--sns-arn", help="AWS SNS Topic ARN for notifications")
    
    args = parser.parse_args()

    drift_detected, details = detect_drift(args.iac_tool, args.iac_dir)

    if drift_detected:
        print(f"!!! DRIFT DETECTED in {args.iac_dir} !!!")
        send_sns_notification(args.sns_arn, args.iac_tool, args.iac_dir, details)
        sys.exit(2) # Exit with specific code for drift
    else:
        print(f"No drift detected in {args.iac_dir}.")
        sys.exit(0)

if __name__ == "__main__":
    main()
