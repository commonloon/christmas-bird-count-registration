The Admin UI doesn't work.  I get a server error when I click on Admin from the registration page.

There should not be an admin button on the registration page.  Normal users shouldn't see any info about the admin interface.

Admins can find the admin UI by visiting the /admin route.

## Action Items for Next Session

1. **Remove admin links/buttons from public templates (security fix)** - Check templates/index.html and templates/base.html for any admin navigation visible to public users
2. **Debug admin route server error** - Check logs and traceback when accessing /admin route to identify the specific error
3. **Verify admin templates exist in templates/admin/ directory** - Ensure all required admin templates are present and properly structured
4. **Update base template navigation to show admin options only for admin users** - Use conditional logic based on user_role == 'admin'
5. **Test admin route functionality after fixes** - Verify admin interface works correctly for authenticated admin users

Priority: Security fix first (remove public admin visibility), then debug functionality.
